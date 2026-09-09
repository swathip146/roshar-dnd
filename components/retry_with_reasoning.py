"""
Retry with reasoning — plan 3.3.

Every failure path in this codebase substituted a canned fallback and continued:
a JSON parse error produced a hardcoded two-choice scenario, an intent parse
error defaulted to `scenario_generation`, an NPC AI failure fell through an
if/else ladder. The model was never told what went wrong, so it could never fix
it — and the player silently got degraded output that looked deliberate.

This replaces "swap in a fallback" with "tell the model precisely what was wrong
and let it correct itself", keeping the fallback only as a last resort after the
retries are exhausted.

The distinction that matters: a fallback hides the failure, a retry surfaces it
to the only party that can act on it.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.logging_config import get_logger

logger = get_logger(__name__)


class ValidationFailure(Exception):
    """Raised by a validator to describe precisely what the model got wrong."""

    def __init__(self, message: str, *, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def as_feedback(self) -> str:
        """The correction message handed back to the model."""
        return f"{self.message}\n{self.hint}".strip()


def extract_json(text: str) -> Any:
    """
    Pull a JSON object out of a model response.

    Tolerates ```json fences and leading prose, both of which models emit even
    under a response schema.
    """
    if not text or not text.strip():
        raise ValidationFailure(
            "You returned an empty response.",
            hint="Return a single JSON object and nothing else.",
        )

    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost brace pair
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as e:
            raise ValidationFailure(
                f"Your response was not valid JSON: {e}",
                hint=("Return ONE JSON object. No prose before or after, no "
                      "trailing commas, and double-quote every key."),
            )

    raise ValidationFailure(
        "No JSON object was found in your response.",
        hint="Return a single JSON object starting with { and ending with }.",
    )


def require_keys(payload: Dict[str, Any], keys: List[str]) -> None:
    """Validator helper: fail with the specific missing keys named."""
    if not isinstance(payload, dict):
        raise ValidationFailure(
            f"Expected a JSON object, got {type(payload).__name__}.",
            hint="Return an object, not a list or a bare value.",
        )
    missing = [k for k in keys if k not in payload]
    if missing:
        raise ValidationFailure(
            f"Your JSON is missing required key(s): {', '.join(missing)}.",
            hint=f"Include every required key: {', '.join(keys)}.",
        )


def generate_with_retry(
    generator: Any,
    messages: List[Any],
    validate: Callable[[str], Any],
    *,
    max_attempts: int = 3,
    fallback: Optional[Callable[[], Any]] = None,
    label: str = "generation",
) -> Tuple[Any, Dict[str, Any]]:
    """
    Call a generator, validating each response and feeding failures back (3.3).

    Args:
        generator: anything with .run(messages=...) -> {"replies": [...]}
        messages: the initial conversation
        validate: parses/validates a reply, raising ValidationFailure with an
            actionable message on rejection
        max_attempts: total attempts including the first
        fallback: called only if every attempt fails; None re-raises
        label: what this is, for the logs

    Returns:
        (result, info) where info records attempts and the errors seen.
    """
    from haystack.dataclasses import ChatMessage

    conversation = list(messages)
    errors: List[str] = []

    for attempt in range(1, max_attempts + 1):
        try:
            reply = generator.run(messages=conversation)
            text = _reply_text(reply)
        except Exception as e:
            errors.append(f"generator error: {e}")
            logger.warning(f"⚠️ {label} attempt {attempt}: generator failed: {e}")
            # A permanent API fault (400 bad request, 403 bad key) will fail
            # identically on every retry, so stop rather than burning the budget.
            # Rate limits and 5xx are retried. This became reachable once
            # GeminiChatGenerator started RAISING instead of returning the error
            # as reply text, which the validator saw as a successful generation.
            if getattr(e, "status_code", None) and not getattr(e, "retryable", True):
                logger.error(
                    f"❌ {label}: permanent API error (HTTP {e.status_code}), "
                    f"not retrying"
                )
                break
            continue

        try:
            result = validate(text)
            if attempt > 1:
                logger.info(f"✅ {label} recovered on attempt {attempt}")
            return result, {"attempts": attempt, "errors": errors,
                            "recovered": attempt > 1, "used_fallback": False}
        except ValidationFailure as failure:
            errors.append(failure.message)
            logger.warning(f"⚠️ {label} attempt {attempt} rejected: {failure.message}")

            if attempt < max_attempts:
                # THE POINT OF 3.3: tell the model what was wrong instead of
                # silently swapping in a canned fallback it never learns from.
                conversation = list(conversation)
                conversation.append(ChatMessage.from_assistant(text[:2000]))
                conversation.append(ChatMessage.from_user(
                    f"That response was rejected.\n\n{failure.as_feedback()}\n\n"
                    f"Correct it and return the full response again."
                ))
        except Exception as e:
            errors.append(f"validator error: {e}")
            logger.warning(f"⚠️ {label} attempt {attempt}: validator raised: {e}")

    logger.error(f"❌ {label} failed after {max_attempts} attempts: {errors}")
    if fallback is not None:
        return fallback(), {"attempts": max_attempts, "errors": errors,
                            "recovered": False, "used_fallback": True}
    raise ValidationFailure(
        f"{label} failed after {max_attempts} attempts: {errors[-1] if errors else '?'}"
    )


def _reply_text(reply: Any) -> str:
    """Pull the text out of whatever shape the generator returned."""
    if isinstance(reply, dict):
        replies = reply.get("replies") or []
        if replies:
            first = replies[0]
            return getattr(first, "text", None) or getattr(first, "content", "") or str(first)
        return ""
    return getattr(reply, "text", None) or str(reply)


class ConversationMemory:
    """
    Persistent message history across turns — plan 3.4.

    Every LLM call was stateless: `llm_utils` flattened all messages into a
    single string, and because Gemini has no system role the system prompt was
    prepended as user text. Even inside a multi-step loop, conversational
    structure was destroyed.

    This keeps a real, bounded message list per thread so the model can see what
    it said last turn rather than being handed a fresh context every time.
    """

    def __init__(self, max_messages: int = 20):
        self.max_messages = max_messages
        self._threads: Dict[str, List[Dict[str, str]]] = {}

    def append(self, thread_id: str, role: str, content: str) -> None:
        if not content:
            return
        history = self._threads.setdefault(thread_id, [])
        history.append({"role": role, "content": content})
        # Bound it, but never drop the opening system message.
        if len(history) > self.max_messages:
            head = [m for m in history[:1] if m["role"] == "system"]
            history[:] = head + history[-(self.max_messages - len(head)):]

    def messages(self, thread_id: str) -> List[Dict[str, str]]:
        return list(self._threads.get(thread_id, []))

    def as_chat_messages(self, thread_id: str) -> List[Any]:
        """The history as Haystack ChatMessages, ready to send."""
        from haystack.dataclasses import ChatMessage

        builders = {
            "system": ChatMessage.from_system,
            "user": ChatMessage.from_user,
            "assistant": ChatMessage.from_assistant,
        }
        out = []
        for message in self.messages(thread_id):
            builder = builders.get(message["role"], ChatMessage.from_user)
            out.append(builder(message["content"]))
        return out

    def clear(self, thread_id: str) -> None:
        self._threads.pop(thread_id, None)

    def summary(self, thread_id: str) -> Dict[str, Any]:
        history = self.messages(thread_id)
        return {
            "thread_id": thread_id,
            "messages": len(history),
            "roles": {r: sum(1 for m in history if m["role"] == r)
                      for r in ("system", "user", "assistant")},
        }


_GLOBAL_MEMORY: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """Shared ConversationMemory instance."""
    global _GLOBAL_MEMORY
    if _GLOBAL_MEMORY is None:
        _GLOBAL_MEMORY = ConversationMemory()
    return _GLOBAL_MEMORY
