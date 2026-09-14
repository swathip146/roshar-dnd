"""
A scripted stand-in for a real LLM chat generator.

WHY THIS EXISTS
---------------
Suite A must exercise the whole game — agents, orchestrator, tools, engine — with
**zero network calls**, deterministically, on every commit. The only thing faked is
the LLM itself; everything below it (dice, the vendored engine, CharacterManager,
the tactical grid, all rules JSON) stays real.

THE CONTRACT THIS MUST SATISFY
------------------------------
Mirrors `config/llm_utils.py::GeminiChatGenerator.run` exactly:

    @component.output_types(replies=List[ChatMessage])
    def run(messages: List[ChatMessage], tools=None) -> {"replies": [ChatMessage]}

Three capabilities, each load-bearing:

1. **Text replies** — `ChatMessage.from_assistant(str)`.
2. **Tool calls** — `ChatMessage.from_assistant(text, tool_calls=[ToolCall(...)])`,
   mirroring `llm_utils.py:585-600`. This is the critical one: the scenario pipeline
   builds a real Haystack `Agent` (`scenario_generator_agent.py:832`) with
   `tools=DM_TOOLS`, `exit_conditions=["text"]`, `max_agent_steps=10`. A text-only
   fake would exit on step 1 and exercise NONE of the 19 DM tools.
3. **Structured output** — when `response_schema` is passed, the reply text must be
   JSON valid against it (SCENARIO_RESPONSE_SCHEMA, INTENT_ANALYSIS_SCHEMA,
   RULING_SCHEMA, NPC_STATS_RESPONSE_SCHEMA).

WHAT THIS DELIBERATELY IS NOT
-----------------------------
Not a recording of real LLM responses. Recorded fixtures rot the moment a prompt
changes and they bake the model's mistakes in as expected behaviour. The policy
objects in `policies.py` read live game state and choose a legal action, so they bind
only to tool *signatures* — the same thing production binds to.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from haystack import component
from haystack.dataclasses import ChatMessage, ToolCall

from config.logging_config import get_logger

logger = get_logger(__name__)


class FakeGeneratorError(RuntimeError):
    """Raised when a fake is asked for something it cannot honestly produce.

    Deliberately loud. A silent fallback here would let a test pass while
    exercising nothing, which is the exact failure mode Suite A exists to catch.
    """


@component
class ScriptedChatGenerator:
    """A drop-in `GeminiChatGenerator` that consults a policy instead of a network.

    `@component` is REQUIRED, not decoration: Haystack's `Agent` introspects
    `__haystack_input__`/`__haystack_output__` when it runs a generator inside a
    pipeline. Without the decorator the Agent raises
    `AttributeError: 'ScriptedChatGenerator' object has no attribute
    '__haystack_input__'` — which is exactly how this was found in Phase 0. The real
    generator carries it too (`config/llm_utils.py:431`).

    Args:
        policy: object with `next_reply(messages, tools, call_index)`. May return a
            `str` (text reply), a `ToolCall`/list of them, or a dict (JSON-encoded).
        response_schema: when set, replies are JSON objects valid against it.
        agent_name: which agent this generator was built for; used in logs and lets
            one policy serve several agents.
        record: a shared list every call is appended to, so tests can assert on what
            the game actually asked the "model" for.
    """

    def __init__(
        self,
        policy: Any,
        response_schema: Optional[Dict[str, Any]] = None,
        agent_name: str = "unknown",
        model_name: str = "fake-model",
        record: Optional[List[Dict[str, Any]]] = None,
    ):
        self.policy = policy
        self.response_schema = response_schema
        self.agent_name = agent_name
        self.model_name = model_name
        self.record = record if record is not None else []
        self.call_count = 0

    # -- the production contract -------------------------------------------------

    @component.output_types(replies=List[ChatMessage])
    def run(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Return one assistant reply, mirroring GeminiChatGenerator.run."""
        index = self.call_count
        self.call_count += 1

        reply = self._ask_policy(messages, tools, index)
        message = self._to_chat_message(reply)

        self.record.append(
            {
                "agent": self.agent_name,
                "call_index": index,
                "n_messages": len(messages or []),
                "n_tools": len(tools or []),
                "tool_calls": [tc.tool_name for tc in (message.tool_calls or [])],
                "text": (message.text or "")[:200],
            }
        )
        logger.debug(
            "🤖 fake[%s] call %d → %s",
            self.agent_name,
            index,
            [tc.tool_name for tc in (message.tool_calls or [])] or "text",
        )
        return {"replies": [message]}

    # -- internals --------------------------------------------------------------

    def _ask_policy(self, messages, tools, index):
        """Get this call's reply from the policy, preferring the richest hook."""
        for attr in ("next_reply", "next_tool_call"):
            hook = getattr(self.policy, attr, None)
            if callable(hook):
                return hook(
                    messages=messages,
                    tools=tools,
                    call_index=index,
                    agent_name=self.agent_name,
                    response_schema=self.response_schema,
                )
        if callable(self.policy):
            return self.policy(messages, tools, index)
        raise FakeGeneratorError(
            f"policy {type(self.policy).__name__} has no next_reply/next_tool_call "
            "and is not callable"
        )

    def _to_chat_message(self, reply: Any) -> ChatMessage:
        """Normalise a policy's return value into one assistant ChatMessage."""
        if isinstance(reply, ChatMessage):
            return reply

        if isinstance(reply, ToolCall):
            return ChatMessage.from_assistant("", tool_calls=[reply])

        if isinstance(reply, (list, tuple)):
            calls = [c for c in reply if isinstance(c, ToolCall)]
            if not calls:
                raise FakeGeneratorError(f"list reply held no ToolCall: {reply!r}")
            return ChatMessage.from_assistant("", tool_calls=calls)

        if isinstance(reply, dict):
            # A structured reply. Emitted as JSON text, which is what the real
            # generator does in response_mime_type=application/json mode.
            return ChatMessage.from_assistant(json.dumps(reply))

        if isinstance(reply, str):
            if self.response_schema and not _looks_like_json(reply):
                raise FakeGeneratorError(
                    f"agent {self.agent_name!r} demands schema-shaped JSON but the "
                    f"policy returned prose: {reply[:120]!r}"
                )
            return ChatMessage.from_assistant(reply)

        raise FakeGeneratorError(f"policy returned unusable {type(reply).__name__}")


def _looks_like_json(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("{") or stripped.startswith("[")


def make_tool_call(name: str, **arguments: Any) -> ToolCall:
    """Build a ToolCall the way `llm_utils.py:587` does.

    Keyword form keeps call sites readable:
        make_tool_call("roll_skill_check", skill="athletics", dc=12)
    """
    return ToolCall(tool_name=name, arguments=dict(arguments))
