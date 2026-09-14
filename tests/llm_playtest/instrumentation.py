"""
Suite B instrumentation — what did the REAL model actually reach?

WHY THIS EXISTS
---------------
Suite A proves every mechanic works: 146 tests, all 57 rows of the strategy's §4, with a
scripted policy standing in for the DM's judgement. A scripted policy is a competent DM
*by construction* — it calls `roll_skill_check` because I told it to.

Suite B answers the question Suite A structurally cannot: **will an actual model, given
the real prompts, ever call these tools?** A mechanic that is correct but never triggered
by the LLM is invisible to players. That is this project's signature failure —
IMPLEMENTED but not REACHABLE — expressed one layer up, in prompts instead of wiring.

**The gap between Suite A and Suite B is the actionable product of this file.**

HOW IT WORKS
------------
`ToolCallRecorder` wraps every `@tool` in `DM_TOOLS` (and the NPC social tool) so each
invocation is recorded with its arguments and whether it raised. Wrapping the `Tool`
objects rather than patching the agent means it observes the same entry point the
Haystack `Agent` uses, so it cannot miss a call the model actually made.

It records only what genuinely happened; it never asserts prose.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ToolCall:
    """One real invocation of a DM tool by the live model."""

    name: str
    arguments: Dict[str, Any]
    ok: bool
    turn: int
    detail: str = ""
    elapsed_ms: int = 0


@dataclass
class ToolCallRecorder:
    """Records every DM-tool invocation made during a live run.

    Wraps the callables behind the Haystack `Tool` objects in place, so the recorder
    sees exactly the calls the Agent makes. `restore()` puts the originals back.
    """

    calls: List[ToolCall] = field(default_factory=list)
    turn: int = 0
    _originals: Dict[int, Any] = field(default_factory=dict, repr=False)
    _tools: List[Any] = field(default_factory=list, repr=False)

    # -- installation --------------------------------------------------------

    def install(self) -> int:
        """Wrap every DM tool. Returns how many were instrumented."""
        from agents.dm_tools import DM_TOOLS

        tools = list(DM_TOOLS)
        try:
            from agents.npc_controller_agent import roll_social_check

            tools.append(roll_social_check)
        except Exception:  # pragma: no cover - social tool optional
            pass

        wrapped = 0
        for tool in tools:
            function = getattr(tool, "function", None)
            if function is None or not callable(function):
                continue
            key = id(tool)
            if key in self._originals:
                continue
            self._originals[key] = function
            self._tools.append(tool)
            tool.function = self._wrap(getattr(tool, "name", "?"), function)
            wrapped += 1

        logger.info("🔎 Suite B: instrumented %d DM tools", wrapped)
        return wrapped

    def restore(self) -> None:
        """Undo the wrapping, so a later run is not doubly instrumented."""
        for tool in self._tools:
            original = self._originals.get(id(tool))
            if original is not None:
                tool.function = original
        self._originals.clear()
        self._tools.clear()

    def _wrap(self, name: str, function):
        def recorded(*args, **kwargs):
            started = time.time()
            try:
                result = function(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
                self.calls.append(ToolCall(
                    name=name, arguments=dict(kwargs), ok=False, turn=self.turn,
                    detail=f"{type(exc).__name__}: {exc}",
                    elapsed_ms=int((time.time() - started) * 1000)))
                raise
            # A tool that returns {"error": ...} ran but refused; that is still a
            # reached tool, so record it as reached with the refusal noted.
            detail = ""
            if isinstance(result, dict):
                detail = str(result.get("error") or "")[:160]
            self.calls.append(ToolCall(
                name=name, arguments=dict(kwargs), ok=True, turn=self.turn,
                detail=detail, elapsed_ms=int((time.time() - started) * 1000)))
            return result

        recorded.__name__ = getattr(function, "__name__", name)
        recorded.__doc__ = function.__doc__
        return recorded

    # -- reading -------------------------------------------------------------

    @property
    def tools_reached(self) -> set:
        return {call.name for call in self.calls}

    @property
    def counts(self) -> Counter:
        return Counter(call.name for call in self.calls)

    def failures(self) -> List[ToolCall]:
        """Calls that RAISED. A tool the model invoked and that crashed is a bug."""
        return [call for call in self.calls if not call.ok]

    def refusals(self) -> List[ToolCall]:
        """Calls that returned an `error` — reached, but declined."""
        return [call for call in self.calls if call.ok and call.detail]

    def summary(self) -> Dict[str, Any]:
        return {
            "total_calls": len(self.calls),
            "distinct_tools": len(self.tools_reached),
            "tools_reached": sorted(self.tools_reached),
            "counts": dict(self.counts),
            "failures": [
                {"tool": c.name, "turn": c.turn, "detail": c.detail}
                for c in self.failures()
            ],
        }


# --------------------------------------------------------------------------- #
# The Suite A ↔ Suite B comparison — the real product of this suite
# --------------------------------------------------------------------------- #

#: Which DM tool, if the model calls it, demonstrates that a §4 mechanic row was
#: reached in live play. Deliberately conservative: only tools whose invocation
#: unambiguously implies the mechanic ran.
TOOL_TO_MECHANIC: Dict[str, List[str]] = {
    "roll_skill_check": ["E1 skills / 7-step pipeline"],
    "get_passive_perception": ["E2 passive perception"],
    "roll_dice": ["E1 dice"],
    "get_character_state": ["character sheet read"],
    "get_party_state": ["party state read"],
    "get_world_state": ["E5 world/clock read"],
    "query_rules": ["E10 rules tiers"],
    "search_lore": ["RAG retrieval"],
    "apply_damage": ["C2 damage application"],
    "apply_healing": ["healing"],
    "take_rest": ["E4 rests"],
    "stabilize_dying": ["C11 stabilising"],
    "spend_stormlight": ["R5 Stormlight economy"],
    "advance_quest": ["E7 quests"],
    "award_experience": ["P1 XP award"],
    "travel_to_location": ["E5 travel"],
    "cast_spell": ["C9 spellcasting"],
    "add_item_to_inventory": ["E8 inventory"],
    "remove_item_from_inventory": ["E8 inventory"],
    "roll_social_check": ["E6 social checks"],
}


def coverage_report(recorder: ToolCallRecorder,
                    suite_a_tools: Optional[set] = None) -> Dict[str, Any]:
    """Compare what the live model reached against what Suite A exercises.

    Args:
        recorder: the instrumented run.
        suite_a_tools: tool names Suite A covers. Defaults to every DM tool, which is
            what Suite A's E11 gate already asserts.
    """
    from agents.dm_tools import DM_TOOLS

    all_tools = {getattr(t, "name") for t in DM_TOOLS if getattr(t, "name", None)}
    all_tools.add("roll_social_check")
    covered_by_a = suite_a_tools if suite_a_tools is not None else set(all_tools)

    reached = recorder.tools_reached
    never = sorted(all_tools - reached)

    return {
        "reached_by_llm": sorted(reached),
        "never_reached_by_llm": never,
        "reach_ratio": (len(reached) / len(all_tools)) if all_tools else 0.0,
        "covered_by_suite_a_only": sorted(covered_by_a - reached),
        "mechanics_reached": sorted({
            m for tool in reached for m in TOOL_TO_MECHANIC.get(tool, [])
        }),
    }


def write_report(path: Path, payload: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info("📝 Suite B report written to %s", path)
    return path
