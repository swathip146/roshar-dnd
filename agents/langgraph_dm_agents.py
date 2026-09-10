"""
LangGraph implementations of the DM agents, drop-in for the Haystack ones.

Migration strategy — deliberately conservative, because the previous three
"delivered" subsystems were the ones nothing called:

Each class here is a DROP-IN for its Haystack counterpart. It exposes the same
`run(messages=[...]) -> {"messages": [...]}` contract and returns objects with the
same `.text` accessor the orchestrator already reads, so switching transports
needs **no changes** to `pipeline_integration.py`, the DTOs, the prompts or the
schemas. That keeps the migration reversible: `LLM_AGENT_BACKEND=haystack` (the
default) or `=langgraph`, one env var, no code edits.

Why migrate at all — a hard constraint, not taste. Haystack 2.21 (pinned) has
`AgentBreakpoint`/`AgentSnapshot`; 3.0 removed them, and current Gemini
integrations require >= 3.0. `requirements.txt` says `haystack-ai>=2.0.0`, so a
fresh clone installs 3.x and these agents break.

What is NOT here: the tool-calling loop for the scenario agent. That agent
already runs a working two-phase adjudicate/narrate split over Haystack with
`max_agent_steps=10`, and porting a working loop is where a silent regression
would hide. It moves once the simpler agents have proven the seam in live play.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

BACKEND_ENV = "LLM_AGENT_BACKEND"


def active_backend() -> str:
    """
    Which agent backend to build: "haystack" (default) or "langgraph".

    Defaults to haystack so that merging this cannot change live behaviour. The
    switch is an env var rather than a code edit so a bad run is one variable away
    from being reverted.
    """
    value = (os.getenv(BACKEND_ENV) or "haystack").strip().lower()
    if value not in {"haystack", "langgraph"}:
        logger.warning(f"⚠️ Unknown {BACKEND_ENV}={value!r}; using haystack")
        return "haystack"
    return value


class _Reply:
    """
    A minimal stand-in for `haystack.dataclasses.ChatMessage`.

    The orchestrator reads a reply through several accessors, having been burned
    by each in turn: `.text`, then `._content` (a list of parts), then `str()`.
    All three are supported here so the consumer needs no branching — and so a
    future Haystack removal cannot break the reader.
    """

    def __init__(self, text: str):
        self.text = text or ""
        self._content = [self]
        self.content = self.text
        self.role = "assistant"

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"_Reply({self.text[:60]!r})"


def _to_langchain(messages: List[Any]) -> List[Any]:
    """
    Convert Haystack ChatMessages (or plain dicts/strings) to LangChain messages.

    Handles dicts explicitly. Passing plain dicts through a converter that only
    understood objects is what produced EMPTY prompts for every NPC-AI call — one
    defect that surfaced as three separate symptoms and was misattributed to
    thinking budgets and Google-side 500s.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    converted: List[Any] = []
    for message in messages or []:
        role, text = _role_and_text(message)
        if not text:
            continue
        if role == "system":
            converted.append(SystemMessage(content=text))
        elif role == "assistant":
            converted.append(AIMessage(content=text))
        else:
            converted.append(HumanMessage(content=text))
    return converted


def _role_and_text(message: Any) -> tuple[str, str]:
    """Best-effort (role, text) for every message shape seen in this codebase."""
    if isinstance(message, str):
        return "user", message
    if isinstance(message, dict):
        role = message.get("role") or "user"
        text = message.get("content") or message.get("text") or ""
        return str(role), str(text)

    role = getattr(message, "role", "user")
    role = getattr(role, "value", role)

    text = getattr(message, "text", None)
    if not text:
        content = getattr(message, "_content", None) or getattr(message, "content", None)
        if isinstance(content, list) and content:
            text = getattr(content[0], "text", None) or str(content[0])
        elif content:
            text = str(content)
    return str(role), str(text or "")


class LangGraphAgent:
    """
    A single-step LangGraph agent: messages in, one reply out.

    Deliberately not a graph for the simple agents — a StateGraph with one node
    adds a checkpointer and a state schema for no benefit. The graph lives where
    it earns its keep: `components/durable_turns.py`, which owns the interrupt and
    the checkpointing.
    """

    def __init__(self, agent_name: str, system_prompt: str = "",
                 response_schema: Optional[Dict[str, Any]] = None,
                 tools: Optional[List[Any]] = None):
        from agents.langgraph_models import create_chat_model

        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self._model = create_chat_model(agent_name,
                                       response_schema=response_schema,
                                       tools=tools)
        logger.info(f"🕸️  LangGraph agent '{agent_name}' ready "
                    f"(tools={len(self.tools)})")

    def run(self, messages: Optional[List[Any]] = None,
            **kwargs) -> Dict[str, Any]:
        """
        Mirror `haystack.components.agents.Agent.run`.

        Returns {"messages": [...]} whose last element exposes `.text`, which is
        what the orchestrator reads.
        """
        converted = _to_langchain(messages or [])

        # Check for an empty request BEFORE prepending the system prompt —
        # otherwise the system message alone makes `converted` non-empty and the
        # guard never fires. An empty prompt is never a legitimate request, and
        # Gemini answers it with something unusable: plain dicts once produced
        # empty prompts for every NPC-AI call, a single defect that surfaced as
        # three symptoms and was misattributed to thinking budgets and
        # Google-side 500s. Fail visibly instead.
        if not converted:
            logger.error(f"❌ {self.agent_name}: refusing to call with an empty "
                         f"prompt (messages={messages!r})")
            return {"messages": [_Reply("")], "error": "empty prompt"}

        if self.system_prompt:
            from langchain_core.messages import SystemMessage
            converted = [SystemMessage(content=self.system_prompt)] + converted

        response = self._model.invoke(converted)
        text = self._text_of(response)
        return {"messages": list(messages or []) + [_Reply(text)],
                "raw": response}

    @staticmethod
    def _text_of(response: Any) -> str:
        """Extract text from a LangChain reply, tolerating list content parts."""
        content = getattr(response, "content", "")
        if isinstance(content, list):
            parts = [part.get("text", "") if isinstance(part, dict) else str(part)
                     for part in content]
            return "".join(parts)
        return str(content or "")


def create_interface_agent_langgraph() -> LangGraphAgent:
    """
    LangGraph drop-in for `create_fixed_interface_agent()`.

    Reuses the Haystack agent's system prompt and schema verbatim — the prompt was
    tuned over several live runs, and re-authoring it would confound a transport
    change with a behaviour change.
    """
    from agents.main_interface_agent_fixed import (INTENT_ANALYSIS_SCHEMA,
                                                   INTERFACE_SYSTEM_PROMPT)

    return LangGraphAgent("main_interface",
                          system_prompt=INTERFACE_SYSTEM_PROMPT,
                          response_schema=INTENT_ANALYSIS_SCHEMA)


def create_npc_agent_langgraph() -> LangGraphAgent:
    """LangGraph drop-in for `create_npc_controller_agent()`."""
    from agents.npc_controller_agent import NPC_SYSTEM_PROMPT

    return LangGraphAgent("npc_controller", system_prompt=NPC_SYSTEM_PROMPT)
