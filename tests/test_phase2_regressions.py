"""
Phase 2 regression tests (docs/REBUILD_PLAN_V5.md §5).

Tier-2 assertions per §12: assert on observable end state, never on
"the method was called."
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.game_engine import GameEngine
from haystack_dnd_game import HaystackDnDGame


PC = {
    "character_id": "aggi",
    "name": "Aggi",
    "level": 3,
    "ability_scores": {"strength": 10, "dexterity": 16, "constitution": 12,
                       "intelligence": 10, "wisdom": 12, "charisma": 14},
    "hit_points": {"current": 24, "maximum": 24, "temporary": 0},
    "armor_class": 14,
    "character_class": "Lightweaver",
    "race": "Alethi",
    "background": "Soldier",
    "skills": {"stealth": True, "perception": True},
}


@pytest.fixture
def engine():
    ge = GameEngine()
    ge.add_character(dict(PC))
    return ge


@pytest.fixture
def game(engine):
    """A HaystackDnDGame with just enough wired for turn-input handling."""
    g = HaystackDnDGame.__new__(HaystackDnDGame)
    g.game_engine = engine
    g.character_manager = engine.character_manager
    g.dnd_engine_wrapper = None
    g.current_choices = []
    return g


# ------------------------------------------------------------------ 2.1 checks

class TestSkillCheckPipelineIsReachable:
    """
    2.1 — GameEngine.process_skill_check() is a complete, tested 7-step
    pipeline that had ZERO production callers. The scenario agent emitted
    suggested_dc and skill_hints on every choice and nothing read either: the
    DC was decorative markdown in the choice title, and no dice were rolled
    outside combat at all.
    """

    def test_pipeline_returns_a_real_roll(self, engine):
        result = engine.process_skill_check(
            {"actor": "aggi", "skill": "stealth", "dc": 13, "context": {}}
        )
        assert 1 <= result["selected_roll"] <= 20, "not a d20 result"
        assert isinstance(result["success"], bool)
        assert result["dc"] > 0

    def test_outcomes_vary_across_rolls(self, engine):
        """A fixed outcome would mean the dice are not actually being rolled."""
        rolls = {
            engine.process_skill_check(
                {"actor": "aggi", "skill": "stealth", "dc": 13, "context": {}}
            )["selected_roll"]
            for _ in range(40)
        }
        assert len(rolls) > 5, f"only saw {sorted(rolls)} — dice look fixed"

    def test_dc_affects_success_rate(self, engine):
        def rate(dc):
            hits = sum(
                engine.process_skill_check(
                    {"actor": "aggi", "skill": "stealth", "dc": dc, "context": {}}
                )["success"]
                for _ in range(60)
            )
            return hits / 60

        assert rate(5) > rate(20), "a DC 5 check must succeed more often than DC 20"


class TestChoiceSelectionRollsDice:
    """The wiring: picking a choice with a DC must roll a real check."""

    def test_choice_with_dc_rolls(self, game):
        game.current_choices = [
            {"title": "Sneak past", "description": "quietly",
             "suggested_dc": 13, "skill_hints": ["stealth"]},
        ]
        result = game._process_input("1")
        assert result["skill_check_result"] is not None, \
            "suggested_dc was ignored — 2.1 regression"
        assert 1 <= result["skill_check_result"]["selected_roll"] <= 20

    def test_outcome_reaches_the_dm_prompt(self, game):
        """The next scene must know whether the check passed."""
        game.current_choices = [
            {"title": "Sneak past", "description": "quietly",
             "suggested_dc": 13, "skill_hints": ["stealth"]},
        ]
        text = game._process_input("1")["processed_input"]
        assert "Skill check:" in text
        assert ("succeeded" in text) or ("failed" in text)
        assert "vs DC" in text

    def test_choice_without_dc_skips_the_check(self, game):
        game.current_choices = [{"title": "Walk up openly", "description": "no risk"}]
        assert game._process_input("1")["skill_check_result"] is None

    def test_zero_dc_skips_the_check(self, game):
        game.current_choices = [
            {"title": "Trivial", "description": "x", "suggested_dc": 0},
        ]
        assert game._process_input("1")["skill_check_result"] is None

    def test_free_text_input_is_untouched(self, game):
        game.current_choices = [
            {"title": "Sneak", "description": "x", "suggested_dc": 13},
        ]
        result = game._process_input("I look around the room")
        assert result["processed_input"] == "I look around the room"
        assert "skill_check_result" not in result

    def test_out_of_range_choice_falls_through(self, game):
        game.current_choices = [{"title": "Only one", "description": "x"}]
        result = game._process_input("7")
        assert result["processed_input"] == "7"

    def test_missing_skill_hints_still_rolls(self, game):
        """A DC with no named skill should become a raw ability check."""
        game.current_choices = [
            {"title": "Force the door", "description": "x", "suggested_dc": 12},
        ]
        assert game._process_input("1")["skill_check_result"] is not None

    def test_check_failure_never_breaks_the_turn(self, game):
        """A broken engine must degrade, not end the session."""
        class _Boom:
            def process_skill_check(self, req):
                raise RuntimeError("engine exploded")

        game.game_engine = _Boom()
        game.current_choices = [
            {"title": "Sneak", "description": "x", "suggested_dc": 13},
        ]
        result = game._process_input("1")
        assert result["skill_check_result"] is None
        assert result["processed_input"].startswith("Sneak")

    def test_both_outcomes_occur_over_many_picks(self, game):
        game.current_choices = [
            {"title": "Sneak", "description": "x",
             "suggested_dc": 13, "skill_hints": ["stealth"]},
        ]
        seen = {game._process_input("1")["skill_check_result"]["success"]
                for _ in range(40)}
        assert seen == {True, False}, f"only ever saw {seen} — dice look fixed"
