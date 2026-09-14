"""
Scripted DM policies — deterministic stand-ins for the model's *judgement*.

WHY POLICIES AND NOT RECORDED RESPONSES
---------------------------------------
A recorded LLM transcript rots the moment a prompt changes, and it encodes the model's
mistakes as expected behaviour. These policies instead read the live tool list and the
live game state and choose a *legal* action. They bind only to tool signatures — the
same contract production binds to — so a prompt rewrite does not touch them, while a
tool-signature change breaks them loudly. That is the desired direction of failure.

Each policy implements:

    next_reply(messages, tools, call_index, agent_name, response_schema) -> reply

where `reply` is a str, a dict (JSON-encoded), a ToolCall, or a list of ToolCalls. See
`fake_generator.ScriptedChatGenerator._to_chat_message`.

THE TWO-PHASE TURN THIS MUST SATISFY
------------------------------------
`scenario_generator_agent` runs a real Haystack `Agent` with `exit_conditions=["text"]`
and `max_agent_steps=10`, then a schema-enforced narration call. So a scenario policy
must (a) emit tool calls for a few steps to exercise the DM tools, then (b) emit text to
exit the loop, and (c) answer the narration call with SCENARIO_RESPONSE_SCHEMA JSON.
A text-only policy exercises none of the 19 DM tools.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from config.logging_config import get_logger

from .fake_generator import make_tool_call

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Canned schema-valid payloads
# --------------------------------------------------------------------------- #

def scenario_json(
    scene: str = "The stormwall grinds east across the Shattered Plains.",
    choices: Optional[List[Dict[str, Any]]] = None,
    gm_notes: str = "Deterministic test scene.",
) -> Dict[str, Any]:
    """A payload valid against SCENARIO_RESPONSE_SCHEMA.

    Required keys are scene/choices/gm_notes; each choice requires
    id/title/description/skill_hints/suggested_dc/combat_trigger
    (`agents/scenario_generator_agent.py:28-81`).
    """
    if choices is None:
        choices = [
            {
                "id": "c1",
                "title": "Press on along the ridge",
                "description": "Keep moving while the light holds.",
                "skill_hints": ["athletics"],
                "suggested_dc": 12,
                "combat_trigger": False,
            },
            {
                "id": "c2",
                "title": "Scout the chasm edge",
                "description": "Look for movement below.",
                "skill_hints": ["perception"],
                "suggested_dc": 13,
                "combat_trigger": False,
            },
        ]
    return {"scene": scene, "choices": choices, "gm_notes": gm_notes, "hooks": []}


def intent_json(
    primary: str = "scenario_action",
    action_verb: str = "explore",
    target: str = "",
    rag_needed: bool = False,
) -> Dict[str, Any]:
    """A payload valid against INTENT_ANALYSIS_SCHEMA."""
    return {
        "primary": primary,
        "action_verb": action_verb,
        "arguments": "",
        "target": target,
        "confidence": 0.9,
        "rationale": "Deterministic classification for the integration suite.",
        "rag_needed": rag_needed,
        "rag_query": "" if not rag_needed else action_verb,
        "rag_filters": "rules,general",
        "rag_confidence": 0.8 if rag_needed else 0.1,
        "rag_category": "general",
    }


def ruling_json(legal: bool = True, dc: int = 12) -> Dict[str, Any]:
    """A payload valid against RULING_SCHEMA (`components/rules_judge.py:50`)."""
    return {
        "legal": legal,
        "reason": "Permitted by the cited rule.",
        "cost": {},
        "resolution": {"type": "check", "skill": "athletics", "dc": dc},
        "cites": ["SRD 5.2.1 — Ability Checks"],
        "confidence": "high",
    }


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #

class BasePolicy:
    """Routes a call to a per-agent handler and answers schemas by shape.

    Subclasses normally override only `scenario_tool_calls()`.
    """

    #: max tool-calling steps before emitting text to exit the Agent loop.
    max_tool_steps = 3

    def __init__(self) -> None:
        self.seen: List[str] = []
        self._scenario_steps = 0

    # -- entry point ---------------------------------------------------------

    def next_reply(
        self,
        messages: Sequence[Any],
        tools: Optional[Sequence[Any]],
        call_index: int,
        agent_name: str,
        response_schema: Optional[Dict[str, Any]],
        **_: Any,
    ) -> Any:
        self.seen.append(agent_name)

        # A schema always wins: the caller cannot parse anything else.
        if response_schema is not None:
            return self._schema_reply(response_schema, agent_name)

        if agent_name == "scenario_generator":
            return self._scenario_reply(messages, tools, call_index)
        if agent_name == "main_interface":
            return intent_json()
        if agent_name in ("npc_controller", "combat_narrative"):
            return self.narration()
        if agent_name == "rag_retriever":
            return "No further lore is relevant to this action."
        if agent_name in ("npc_combat_ai", "combat_init"):
            return self.combat_ai_reply()
        return self.narration()

    # -- per-agent behaviour -------------------------------------------------

    def _schema_reply(self, schema: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
        """Pick a canned payload by inspecting the schema's required keys."""
        required = set(schema.get("required") or ())
        properties = set((schema.get("properties") or {}).keys())

        if {"scene", "choices"} & required or {"scene", "choices"} <= properties:
            return scenario_json()
        if "primary" in properties:
            return intent_json()
        if "legal" in required or "cites" in required:
            return ruling_json()
        if {"armor_class", "hit_points"} & properties or "stats" in properties:
            return self.npc_stats_json(schema)
        logger.warning("🧪 unrecognised schema for %s; returning {}", agent_name)
        return {}

    def _scenario_reply(self, messages, tools, call_index) -> Any:
        """Emit tool calls for a few steps, then text so the Agent loop exits."""
        if not tools:
            return self.narration()
        if self._scenario_steps >= self.max_tool_steps:
            return self.summary()
        self._scenario_steps += 1
        call = self.scenario_tool_calls(messages, tools, self._scenario_steps - 1)
        return call if call is not None else self.summary()

    # -- overridable hooks ---------------------------------------------------

    def scenario_tool_calls(self, messages, tools, step: int) -> Any:
        """Which DM tool to call on this step. None → stop and summarise."""
        available = {getattr(t, "name", None) for t in (tools or [])}
        plan = [
            make_tool_call("get_character_state", character_name="Aggi"),
            make_tool_call("get_world_state"),
        ]
        if step < len(plan) and plan[step].tool_name in available:
            return plan[step]
        return None

    def summary(self) -> str:
        return "The party advances; no rolls were required."

    def narration(self) -> str:
        return "Stormlight guttered along the rockbuds as the party moved."

    def npc_stats_json(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Minimal NPC_STATS_RESPONSE_SCHEMA payload."""
        return {
            "name": "Test Adversary",
            "armor_class": 13,
            "hit_points": 11,
            "challenge_rating": "1/4",
            "abilities": {"STR": 12, "DEX": 12, "CON": 12,
                          "INT": 8, "WIS": 10, "CHA": 8},
            "attacks": [{"name": "Spear", "damage": "1d6", "damage_type": "piercing"}],
        }

    def combat_ai_reply(self) -> Any:
        return '{"action": "attack", "target": "nearest", "rationale": "closest foe"}'


# --------------------------------------------------------------------------- #
# Concrete policies
# --------------------------------------------------------------------------- #

class NarrateOnlyPolicy(BasePolicy):
    """Never calls a tool. Baseline for testing the pipeline shell itself."""
    max_tool_steps = 0


class SkillCheckPolicy(BasePolicy):
    """Rolls a real skill check through the 7-step pipeline, then summarises.

    Exercises E1: `roll_skill_check` -> `game_engine.process_skill_check`.
    """

    def __init__(self, skill: str = "athletics", dc: int = 12,
                 character: str = "Aggi") -> None:
        super().__init__()
        self.skill, self.dc, self.character = skill, dc, character
        self.max_tool_steps = 2

    def scenario_tool_calls(self, messages, tools, step):
        available = {getattr(t, "name", None) for t in (tools or [])}
        if step == 0 and "roll_skill_check" in available:
            return make_tool_call(
                "roll_skill_check",
                skill=self.skill, dc=self.dc, character_name=self.character,
            )
        return None

    def summary(self) -> str:
        return f"{self.character} attempted a {self.skill} check against DC {self.dc}."


class ToolSequencePolicy(BasePolicy):
    """Calls an explicit list of tools in order — the workhorse for coverage.

        ToolSequencePolicy([
            make_tool_call("get_party_state"),
            make_tool_call("take_rest", rest_type="long"),
        ])

    A tool absent from the live list is skipped with a warning rather than
    failing, so one policy can serve differently-equipped pipelines.
    """

    def __init__(self, calls: Sequence[Any], summary: str = "Actions resolved.") -> None:
        super().__init__()
        self.calls = list(calls)
        self._summary = summary
        self.max_tool_steps = len(self.calls) + 1
        self.executed: List[str] = []

    def scenario_tool_calls(self, messages, tools, step):
        available = {getattr(t, "name", None) for t in (tools or [])}
        while step < len(self.calls):
            call = self.calls[step]
            if call.tool_name in available:
                self.executed.append(call.tool_name)
                return call
            logger.warning("🧪 tool %s not offered; skipping", call.tool_name)
            step += 1
        return None

    def summary(self) -> str:
        return self._summary


class CombatIntentPolicy(BasePolicy):
    """Classifies input as combat so the orchestrator routes into the combat path."""

    def next_reply(self, messages, tools, call_index, agent_name,
                   response_schema, **kw):
        if agent_name == "main_interface" or (
            response_schema and "primary" in (response_schema.get("properties") or {})
        ):
            self.seen.append(agent_name)
            return intent_json(primary="combat", action_verb="attack",
                               target="enemy")
        return super().next_reply(messages, tools, call_index, agent_name,
                                 response_schema, **kw)


class AlwaysAttackPolicy(CombatIntentPolicy):
    """Combat-routing plus an NPC AI that always attacks the nearest foe."""

    def combat_ai_reply(self) -> Any:
        return ('{"action": "attack", "target": "nearest", '
                '"rationale": "engage the closest threat"}')
