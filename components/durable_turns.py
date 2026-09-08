"""
Durable turn loop — plan 3.5, decision D4.

A game turn blocks on a human for minutes or days. That means turn state must
survive process exit and resume in a NEW process. LangGraph's `interrupt()` plus
a `SqliteSaver` checkpointer is exactly that primitive: resume is a fresh client
call keyed only by `thread_id`, so nothing in-memory needs to survive.

Why LangGraph rather than staying on Haystack (plan §4): Haystack 2.21 shipped
AgentBreakpoint/AgentSnapshot, but 3.0 REMOVED them — "pausing and resuming
execution inside an Agent is no longer supported". Freezing on 2.21 also pins us
below the minimum for current Gemini integrations. Upgrading is a breaking
migration either way, and only one direction keeps durable resume.

THE GOTCHA THIS FILE IS BUILT AROUND: on resume LangGraph RE-EXECUTES the node
from the top. So `interrupt()` gets its own node with nothing else in it, and
dice rolls / LLM calls / state mutation live in separate nodes. Otherwise a
resumed turn re-rolls dice and re-bills tokens.

Haystack is retained for RAG (§4); retrieval is exposed as a tool, not replaced.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict

from config.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHECKPOINT_DB = PROJECT_ROOT / "game_saves" / "turns.sqlite"


class TurnState(TypedDict, total=False):
    """
    State carried across a turn.

    Deliberately small and JSON-serialisable: it is checkpointed on every node
    transition. Live components stay OUT of it — the graph holds ids and turn
    data, while GameEngine/CharacterManager remain the authorities (preserving
    the component-authority design, §4).
    """
    thread_id: str
    turn_number: int
    player_input: str
    active_character: str
    awaiting_input_for: Optional[str]
    prompt: Optional[str]
    choices: List[Dict[str, Any]]
    narration: str
    state_delta: Dict[str, Any]
    status: str            # "ok" | "awaiting_input" | "ended"
    history: List[str]


class DurableTurnLoop:
    """
    A checkpointed turn loop (plan 3.5).

    Usage:
        loop = DurableTurnLoop(on_resolve=game.resolve_turn)
        result = loop.start("campaign-1", "I look around")
        # ... process exits, days pass, a new process starts ...
        result = loop.resume("campaign-1", "2")
    """

    def __init__(self, on_resolve: Optional[Callable[[TurnState], Dict[str, Any]]] = None,
                 checkpoint_db: Path = DEFAULT_CHECKPOINT_DB):
        self.on_resolve = on_resolve
        self.checkpoint_db = Path(checkpoint_db)
        self.checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
        self._graph = None
        self._saver = None
        self._conn = None
        self._build()

    # ------------------------------------------------------------------ graph

    def _build(self) -> bool:
        try:
            from langgraph.graph import StateGraph, END
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as e:
            logger.warning(f"⚠️ LangGraph unavailable, durable turns disabled: {e}")
            return False

        # check_same_thread=False: the checkpointer is read from whichever
        # process resumes the thread, which is the whole point.
        self._conn = sqlite3.connect(str(self.checkpoint_db), check_same_thread=False)
        self._saver = SqliteSaver(self._conn)

        graph = StateGraph(TurnState)
        graph.add_node("await_player", self._node_await_player)
        graph.add_node("resolve", self._node_resolve)
        graph.add_node("finalize", self._node_finalize)

        graph.set_entry_point("await_player")
        graph.add_edge("await_player", "resolve")
        graph.add_edge("resolve", "finalize")
        graph.add_edge("finalize", END)

        self._graph = graph.compile(checkpointer=self._saver)
        logger.info(f"🔁 Durable turn loop ready (checkpoints: {self.checkpoint_db})")
        return True

    @property
    def available(self) -> bool:
        return self._graph is not None

    # ------------------------------------------------------------------ nodes

    @staticmethod
    def _node_await_player(state: TurnState) -> Dict[str, Any]:
        """
        Block for the player's input.

        THIS NODE CONTAINS NOTHING ELSE. On resume LangGraph re-executes the node
        from the top, so anything expensive or random here would run twice: a
        resumed turn would re-roll its dice and re-bill its tokens.
        """
        from langgraph.types import interrupt

        if state.get("player_input"):
            # Input already supplied (the opening call) — nothing to wait for.
            return {"awaiting_input_for": None}

        answer = interrupt({
            "awaiting_input_for": state.get("active_character", ""),
            "prompt": state.get("prompt") or "What do you do?",
            "choices": state.get("choices", []),
            "turn_number": state.get("turn_number", 0),
        })
        return {"player_input": answer if isinstance(answer, str) else str(answer),
                "awaiting_input_for": None}

    def _node_resolve(self, state: TurnState) -> Dict[str, Any]:
        """Resolve the turn. All dice, LLM calls and mutation happen HERE."""
        if self.on_resolve is None:
            return {"narration": f"(no resolver) {state.get('player_input', '')}",
                    "state_delta": {}}
        try:
            result = self.on_resolve(state) or {}
            return {
                "narration": result.get("narration", ""),
                "choices": result.get("choices", []),
                "state_delta": result.get("state_delta", {}),
                "status": result.get("status", "ok"),
            }
        except Exception as e:
            logger.error(f"❌ Turn resolution failed: {e}")
            return {"narration": f"(the turn could not be resolved: {e})",
                    "status": "error", "state_delta": {}}

    @staticmethod
    def _node_finalize(state: TurnState) -> Dict[str, Any]:
        """Record the beat and hand the turn back."""
        history = list(state.get("history", []))
        narration = state.get("narration", "")
        if narration:
            history.append(f"[T{state.get('turn_number', 0)}] {narration[:200]}")
            del history[:-20]
        return {
            "history": history,
            "turn_number": state.get("turn_number", 0) + 1,
            # Clear the input so the next turn interrupts rather than reusing it.
            "player_input": "",
            "status": state.get("status", "ok"),
        }

    # ------------------------------------------------------------------- api

    @staticmethod
    def _config(thread_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def start(self, thread_id: str, player_input: str = "",
              active_character: str = "", turn_number: int = 1) -> Dict[str, Any]:
        """Begin (or continue) a campaign thread with a turn of input."""
        if not self.available:
            return {"status": "unavailable",
                    "error": "LangGraph not installed; durable turns disabled"}
        state: TurnState = {
            "thread_id": thread_id,
            "turn_number": turn_number,
            "player_input": player_input,
            "active_character": active_character,
            "history": [],
            "status": "ok",
        }
        return self._run(self._graph.invoke(state, self._config(thread_id)),
                         thread_id)

    def resume(self, thread_id: str, player_input: str) -> Dict[str, Any]:
        """
        Resume a paused turn in ANY process (plan 3.5 / D4).

        Keyed only by thread_id: nothing in memory needs to have survived.
        """
        if not self.available:
            return {"status": "unavailable"}
        from langgraph.types import Command

        return self._run(
            self._graph.invoke(Command(resume=player_input),
                               self._config(thread_id)),
            thread_id,
        )

    def _run(self, result: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
        """Normalise a graph result into the D4 TurnResult contract."""
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            payload = getattr(interrupts[0], "value", {}) or {}
            return {
                "status": "awaiting_input",
                "thread_id": thread_id,
                "awaiting_input_for": payload.get("awaiting_input_for"),
                "prompt": payload.get("prompt"),
                "choices": payload.get("choices", []),
                "turn_number": payload.get("turn_number"),
            }
        return {
            "status": result.get("status", "ok"),
            "thread_id": thread_id,
            "narration": result.get("narration", ""),
            "choices": result.get("choices", []),
            "state_delta": result.get("state_delta", {}),
            "turn_number": result.get("turn_number"),
            "history": result.get("history", []),
        }

    def get_state(self, thread_id: str) -> Dict[str, Any]:
        """The checkpointed state of a thread, without advancing it."""
        if not self.available:
            return {}
        try:
            snapshot = self._graph.get_state(self._config(thread_id))
            return dict(snapshot.values or {})
        except Exception as e:
            logger.warning(f"⚠️ Could not read thread {thread_id}: {e}")
            return {}

    def list_threads(self) -> List[str]:
        """Every campaign thread with a checkpoint (for a save picker)."""
        if self._conn is None:
            return []
        try:
            rows = self._conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints"
            ).fetchall()
            return sorted(r[0] for r in rows)
        except Exception:
            return []

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
