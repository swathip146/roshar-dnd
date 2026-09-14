"""
Passive Perception must be reachable, and preferred over a roll when not searching.

WHY THIS EXISTS
---------------
A live Suite B run never called `get_passive_perception`, and I first wrote that off as
"situational". It was not. Two real defects:

1. **The scenario prompt never mentioned the tool at all** — not in the workflow, not in
   the action map. The model had no trigger for it.
2. **The tool's description was purely definitional.** It explained what Passive
   Perception *is* ("10 + Wisdom modifier + proficiency") and never said when a DM
   should call it, so the model had nothing to match an intent against.

The visible consequence was a rules error, not just a missing tool call: asked
*"do I notice anything as we pass, without stopping to look?"* the model called
`roll_skill_check`. 5e uses a passive score there precisely so a character who is merely
walking is NOT given a fresh chance to spot something — rolling gives a distracted
character better odds than their passive score says they should have, and worse odds than
it guarantees.

After fixing the prompt and the description, measured live 3/3:

    "do I notice anything as we pass, without stopping to look?"  -> passive ✅
    "we keep marching toward the warcamp, not looking for anything" -> passive ✅
    "I stop and carefully search the rubble for hidden compartments" -> roll ✅

These tests need no LLM — they pin the tool's contract and the guidance the model reads.
The behavioural check lives in Suite B (`--full-coverage`).
"""

from __future__ import annotations

import pytest

from agents.dm_tools import DM_TOOLS, set_dm_tool_context
from tests.integration.harness.game_builder import build_engine, character_template

pytestmark = pytest.mark.integration


@pytest.fixture
def tools():
    engine = build_engine(characters=[character_template()])
    set_dm_tool_context(game_engine=engine,
                        character_manager=engine.character_manager)
    return {getattr(t, "name"): t for t in DM_TOOLS if getattr(t, "name", None)}


class TestPassivePerceptionIsUsable:

    def test_the_tool_returns_a_real_score(self, tools):
        result = tools["get_passive_perception"].invoke(actor="aggi")

        assert not result.get("error"), result
        score = result["passive_perception"]
        assert 5 <= int(score) <= 30, f"implausible passive score: {result}"
        assert result.get("breakdown"), "no breakdown to show the player"

    def test_the_score_is_ten_plus_the_modifier(self, tools):
        """5e: 10 + WIS modifier (+ proficiency). Guards a silent formula change."""
        result = tools["get_passive_perception"].invoke(actor="aggi")
        breakdown = str(result["breakdown"])

        assert breakdown.startswith("10 "), (
            f"passive perception must start from 10: {breakdown!r}")
        assert str(result["passive_perception"]) in breakdown

    def test_the_description_says_WHEN_to_use_it(self):
        """A definitional description left the model with no trigger to match.

        This is the defect that made the tool unreachable in live play, so it is worth
        pinning: the description must distinguish the passive case from the active one.
        """
        tool = next(t for t in DM_TOOLS
                    if getattr(t, "name", None) == "get_passive_perception")
        description = (tool.description or "").lower()

        assert "roll_skill_check" in description, (
            "the description must contrast itself with rolling, or the model cannot "
            "tell which of the two to choose")
        assert "not actively searching" in description or "without rolling" in description, (
            "the description must name the passive case explicitly")

    def test_the_scenario_prompt_teaches_the_distinction(self):
        """The prompt never mentioned this tool, so the model never reached for it."""
        from agents.scenario_generator_agent import create_scenario_generator_agent
        import inspect

        source = inspect.getsource(
            inspect.getmodule(create_scenario_generator_agent))

        assert "get_passive_perception" in source, (
            "the scenario prompt must name get_passive_perception; without it the "
            "model has no trigger and rolls for everything")
        assert "PASSIVE PERCEPTION" in source, (
            "the prompt should state the passive-vs-active rule explicitly")


class TestStabilizeDyingIsUsable:
    """The other 'situational' tool — verified genuinely situational, not broken."""

    def test_it_stabilises_a_character_at_zero_hp(self, tools):
        engine = build_engine(characters=[character_template()])
        set_dm_tool_context(game_engine=engine,
                            character_manager=engine.character_manager)
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 0

        result = {getattr(t, "name"): t for t in DM_TOOLS}["stabilize_dying"].invoke(
            actor="aggi")

        assert result.get("stabilized") is True, result
        assert result.get("is_stable") is True
        assert result.get("is_dead") is False
        assert character.hit_points["current"] == 0, (
            "stabilising must NOT heal — the character stays unconscious at 0 HP")

    def test_the_description_names_its_trigger(self):
        """Unlike passive perception, this one already said when to use it."""
        tool = next(t for t in DM_TOOLS
                    if getattr(t, "name", None) == "stabilize_dying")
        description = (tool.description or "").lower()

        assert "0 hit points" in description or "at 0" in description, (
            "the description must name the 0-HP trigger")
