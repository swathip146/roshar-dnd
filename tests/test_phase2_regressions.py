"""
Phase 2 regression tests (docs/REBUILD_PLAN_V5.md §5).

Tier-2 assertions per §12: assert on observable end state, never on
"the method was called."
"""

import json
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

    def test_requested_dc_is_honoured(self, engine):
        """
        `dc = rules_result.dc` used to overwrite the caller's DC
        unconditionally, so the LLM's suggested_dc was silently discarded and
        EVERY check resolved against the Rules Enforcer's derived value.
        Measured before the fix: DC 5 and DC 25 both became 14 and both
        succeeded ~58% of the time -- difficulty had no effect at all.
        """
        for requested in (5, 15, 25):
            effective = engine.process_skill_check(
                {"actor": "aggi", "skill": "stealth", "dc": requested, "context": {}}
            )["dc"]
            # The policy profile may shift the DC slightly; it must not be ignored.
            assert abs(effective - requested) <= 2, (
                f"requested DC {requested} resolved as {effective} — "
                "the caller's DC is being discarded"
            )

    def test_difficulty_spans_a_real_range(self, engine):
        def rate(dc):
            return sum(
                engine.process_skill_check(
                    {"actor": "aggi", "skill": "stealth", "dc": dc, "context": {}}
                )["success"]
                for _ in range(150)
            ) / 150

        easy, hard = rate(5), rate(25)
        assert easy > 0.85, f"a DC 5 check should almost always pass, got {easy:.0%}"
        assert hard < 0.40, f"a DC 25 check should usually fail, got {hard:.0%}"


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


# ------------------------------------------------------------- 2.2 narrative memory

class TestNarrativeMemory:
    """
    2.2 — `last_scenario` is a SINGLE overwritten slot, so turn N-2 was
    unrecoverable: the DM had a one-turn memory. `narrative_beats` was declared
    in the state schema and never written or read by anything.
    """

    def _play(self, engine, turns):
        for t in range(1, turns + 1):
            engine.process_scenario_state_updates(
                {"scene": f"Scene {t}: the highstorm draws closer.",
                 "choices": [], "gm_notes": ""},
                t,
            )

    def test_beats_are_recorded(self, engine):
        self._play(engine, 3)
        assert len(engine.get_narrative_beats(10)) == 3, \
            "narrative_beats is still never written"

    def test_more_than_one_turn_is_remembered(self, engine):
        """The whole point: turn N-2 must survive."""
        self._play(engine, 3)
        joined = "\n".join(engine.get_narrative_beats(10))
        assert "Scene 1" in joined and "Scene 3" in joined

    def test_history_is_bounded(self, engine):
        self._play(engine, 40)
        stored = engine.game_state.narrative_context["narrative_beats"]
        assert len(stored) <= engine.MAX_NARRATIVE_BEATS, \
            "unbounded history would grow the prompt without limit"

    def test_bounded_history_keeps_the_newest(self, engine):
        self._play(engine, 40)
        joined = "\n".join(engine.get_narrative_beats(50))
        assert "Scene 40" in joined
        assert "Scene 1]" not in joined, "oldest beats should have been dropped"

    def test_beats_are_turn_stamped(self, engine):
        self._play(engine, 2)
        assert engine.get_narrative_beats(10)[0].startswith("[Turn 1]")

    def test_long_scenes_are_summarised(self, engine):
        engine.process_scenario_state_updates(
            {"scene": "x" * 5000, "choices": [], "gm_notes": ""}, 1
        )
        beat = engine.get_narrative_beats(1)[0]
        assert len(beat) < engine.BEAT_SUMMARY_CHARS + 100

    def test_empty_scene_records_nothing(self, engine):
        engine.process_scenario_state_updates({"scene": "", "choices": []}, 1)
        assert engine.get_narrative_beats(10) == []

    def test_story_so_far_is_a_readable_block(self, engine):
        self._play(engine, 4)
        story = engine.get_story_so_far(3)
        assert story.count("\n") == 2, "expected 3 beats joined by newlines"
        assert "Scene 4" in story

    def test_story_reaches_the_dm_prompt(self, engine):
        """Memory is useless if the prompt never sees it."""
        from agents.scenario_generator_agent import create_scenario_from_dto

        self._play(engine, 12)
        prompt = create_scenario_from_dto(
            {"player_input": "look around", "_game_engine_ref": engine, "rag": {}}
        )
        assert "STORY SO FAR" in prompt
        assert "Scene 12" in prompt
        assert "Scene 9" in prompt, "only the latest turn reached the prompt"

    def test_opening_scene_says_so(self, engine):
        from agents.scenario_generator_agent import create_scenario_from_dto

        prompt = create_scenario_from_dto(
            {"player_input": "look", "_game_engine_ref": engine, "rag": {}}
        )
        assert "This is the opening scene." in prompt


# ---------------------------------------------------------------- 2.4 real NPCs

class TestNPCDialogueIsReal:
    """
    2.4 — generate_npc_response ignored the model and returned a hardcoded
    f"The {npc_id} responds to your action...". Because it is the agent's EXIT
    CONDITION, that literal placeholder is what the player saw; the LLM's own
    prose never reached them. npc_context was also always {}, so the agent was
    told to "remember past interactions" with no history at all.
    """

    def _respond(self, **kw):
        from agents.npc_controller_agent import generate_npc_response
        base = {
            "npc_id": "Kalak",
            "player_action": "I greet him",
            "dialogue": "Ah. Another who bears the weight. Sit, if you must.",
            "npc_context": {"personality": "weary"},
        }
        base.update(kw)
        return generate_npc_response.function(**base)

    def test_model_dialogue_is_returned_verbatim(self):
        line = "Storms, you again. What do you want?"
        assert self._respond(dialogue=line)["dialogue"] == line

    def test_placeholder_is_gone(self):
        assert "responds to your action" not in self._respond()["dialogue"]

    def test_dialogue_is_a_required_argument(self):
        """The model must be forced to write the words."""
        import inspect
        from agents.npc_controller_agent import generate_npc_response

        fn = generate_npc_response.function
        params = inspect.signature(fn).parameters
        assert params["dialogue"].default is inspect.Parameter.empty, \
            "dialogue must be required, or the model can omit it and get filler"

    def test_empty_dialogue_degrades_honestly(self):
        """Better a visible 'says nothing' than invented filler prose."""
        result = self._respond(dialogue="   ")
        assert "responds to your action" not in result["dialogue"]
        assert "Kalak" in result["dialogue"]

    def test_attitude_change_is_carried_through(self):
        assert self._respond(attitude_change=2)["attitude_change"] == 2

    def test_prompt_demands_actual_words(self):
        """
        Assert on the PROMPT, not on `inspect.getsource` of the factory.

        This previously grepped the function body, so hoisting the prompt to a
        module constant (so the LangGraph backend could reuse it verbatim) broke
        it while the behaviour was identical. Two Phase-3 tests failed the same
        way before; §14's corollary is that source-grepping tests break on
        refactors and would equally pass on a call that does nothing.
        """
        from agents.npc_controller_agent import NPC_SYSTEM_PROMPT

        assert "YOU WRITE THE WORDS" in NPC_SYSTEM_PROMPT, (
            "the NPC prompt no longer demands actual dialogue, so the LLM will "
            "describe speech instead of writing it")


class TestNPCMemory:
    """2.4 — attitude and history must survive between conversations."""

    @pytest.fixture
    def orch(self):
        import logging
        from orchestrator.pipeline_integration import PipelineOrchestrator

        o = PipelineOrchestrator.__new__(PipelineOrchestrator)
        o.game_engine = None
        o._npc_memory = {}
        o.logger = logging.getLogger("test")
        return o

    def test_context_is_never_empty(self, orch):
        ctx = orch._build_npc_context("Kalak")
        assert ctx, "npc_context was always {} — the 2.4 regression"
        assert "attitude_toward_player" in ctx and "personality" in ctx

    def test_interactions_are_remembered(self, orch):
        for i in range(3):
            orch._remember_npc_interaction(
                "Kalak", f"question {i}", {"dialogue": f"reply {i}"}
            )
        assert len(orch._build_npc_context("Kalak")["recent_interactions"]) == 3

    def test_memory_is_bounded(self, orch):
        for i in range(50):
            orch._remember_npc_interaction("Kalak", f"q{i}", {"dialogue": f"r{i}"})
        stored = orch._build_npc_context("Kalak")["recent_interactions"]
        assert len(stored) <= orch._MAX_NPC_MEMORY

    def test_attitude_accumulates_positive(self, orch):
        for _ in range(3):
            orch._remember_npc_interaction(
                "Kalak", "a kindness", {"dialogue": "x", "attitude_change": 2}
            )
        assert orch._build_npc_context("Kalak")["attitude_toward_player"] == "helpful"

    def test_attitude_accumulates_negative(self, orch):
        for _ in range(3):
            orch._remember_npc_interaction(
                "Kalak", "an insult", {"dialogue": "x", "attitude_change": -2}
            )
        assert orch._build_npc_context("Kalak")["attitude_toward_player"] == "hostile"

    def test_attitude_starts_neutral(self, orch):
        assert orch._build_npc_context("Nale")["attitude_toward_player"] == "neutral"

    def test_npcs_have_separate_memories(self, orch):
        orch._remember_npc_interaction("Kalak", "hi", {"dialogue": "x", "attitude_change": 3})
        assert orch._build_npc_context("Nale")["attitude_toward_player"] == "neutral"

    def test_lookup_is_case_insensitive(self, orch):
        orch._remember_npc_interaction("Kalak", "hi", {"dialogue": "x"})
        assert orch._build_npc_context("KALAK")["recent_interactions"]

    def test_memory_failure_never_breaks_the_turn(self, orch):
        orch._npc_memory = None  # force the lazy-init path
        orch._remember_npc_interaction("Kalak", "hi", {"dialogue": "x"})
        assert orch._build_npc_context("Kalak") is not None


# ------------------------------------------------------------------ 2.3 quests

class TestQuestProgression:
    """
    2.3 — quests were read-only prompt decoration. Two bugs:
      1. the handler only read state_changes["quest_objectives"], but the prompt
         template told the model to emit "quests" — so every quest update the
         LLM produced was silently discarded;
      2. complete_quest_objective() had ZERO callers, so nothing ever moved an
         objective from pending to completed.
    """

    def _update(self, engine, quests, turn=1):
        engine.process_scenario_state_updates(
            {"scene": "s", "choices": [], "state_changes": {"quests": quests}}, turn
        )

    def test_objectives_added_via_the_prompts_key(self, engine):
        self._update(engine, {"add": ["Find the artifact", "Speak to Kalak"]})
        assert engine.get_quest_progress()["pending_count"] == 2, \
            'the "quests" key is still being discarded'

    def test_objective_can_be_completed(self, engine):
        self._update(engine, {"add": ["Find the artifact"]})
        self._update(engine, {"complete": ["Find the artifact"]}, turn=2)
        progress = engine.get_quest_progress()
        assert progress["completed"] == ["Find the artifact"]
        assert progress["pending"] == []

    def test_progress_percentage(self, engine):
        self._update(engine, {"add": ["A", "B", "C", "D"]})
        self._update(engine, {"complete": ["A"]}, turn=2)
        assert engine.get_quest_progress()["percent_complete"] == 25

    def test_legacy_key_still_works(self, engine):
        engine.process_scenario_state_updates(
            {"scene": "s", "state_changes": {"quest_objectives": ["Legacy"]}}, 1
        )
        assert "Legacy" in engine.get_quest_progress()["pending"]

    def test_bare_string_is_accepted(self, engine):
        self._update(engine, "Just one objective")
        assert engine.get_quest_progress()["pending_count"] == 1

    def test_plain_list_is_accepted(self, engine):
        self._update(engine, ["First", "Second"])
        assert engine.get_quest_progress()["pending_count"] == 2

    def test_per_item_status_is_honoured(self, engine):
        self._update(engine, {"add": ["Slay the Fused"]})
        self._update(engine, [{"text": "Slay the Fused", "status": "completed"}], turn=2)
        assert engine.get_quest_progress()["completed"] == ["Slay the Fused"]

    def test_malformed_updates_do_not_raise(self, engine):
        for junk in (None, 12345, {"nonsense": True}, [None]):
            self._update(engine, junk)  # must not raise
        assert isinstance(engine.get_quest_progress()["pending_count"], int)

    def test_completing_an_unknown_objective_is_harmless(self, engine):
        self._update(engine, {"complete": ["Never existed"]})
        assert engine.get_quest_progress()["completed_count"] == 0

    def test_empty_progress_is_zero_not_a_crash(self, engine):
        progress = engine.get_quest_progress()
        assert progress["total"] == 0 and progress["percent_complete"] == 0


# ------------------------------------------- 2.5 XP, levels, rests, death saves

from components.character_manager import CharacterManager


@pytest.fixture
def manager():
    m = CharacterManager()
    m.add_character({
        "character_id": "aggi", "name": "Aggi", "level": 1,
        "ability_scores": {"strength": 12, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 10, "charisma": 14},
        "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
        "armor_class": 13, "character_class": "Lightweaver",
        "race": "Alethi", "background": "Soldier",
        "radiant_order": "Lightweaver", "ideal_level": 1,
    })
    return m


class TestExperienceAndLevelling:
    """
    2.5 — XP and levelling were ENTIRELY absent: grep for award_xp / def
    level_up returned zero hits, so characters were permanently level 1 with
    their starting HP. D6 requires a 1-10 progression.
    """

    def test_xp_is_recorded(self, manager):
        assert manager.award_xp("aggi", 100)["xp"] == 100

    def test_crossing_a_threshold_levels_up(self, manager):
        result = manager.award_xp("aggi", 300)
        assert result["level"] == 2 and result["leveled_up"] is True

    def test_multiple_levels_at_once(self, manager):
        result = manager.award_xp("aggi", 6500)
        assert result["level"] == 5
        assert result["levels_gained"] == 4

    def test_level_up_raises_max_hp(self, manager):
        before = manager.characters["aggi"].hit_points["maximum"]
        manager.award_xp("aggi", 6500)
        assert manager.characters["aggi"].hit_points["maximum"] > before

    def test_proficiency_bonus_scales(self, manager):
        manager.award_xp("aggi", 6500)  # level 5
        assert manager.characters["aggi"].proficiency_bonus == 3

    def test_stormlight_capacity_scales_for_radiants(self, manager):
        manager.award_xp("aggi", 6500)  # level 5
        assert manager.characters["aggi"].stormlight_capacity == 10

    def test_no_level_up_below_threshold(self, manager):
        assert manager.award_xp("aggi", 299)["leveled_up"] is False

    def test_xp_to_next_level(self, manager):
        manager.award_xp("aggi", 300)  # level 2, next at 900
        assert manager.xp_to_next_level("aggi") == 600

    def test_level_caps_at_20(self, manager):
        manager.award_xp("aggi", 10_000_000)
        assert manager.characters["aggi"].level == 20
        assert manager.xp_to_next_level("aggi") is None

    def test_unknown_character_is_graceful(self, manager):
        assert "error" in manager.award_xp("nobody", 100)


class TestRests:
    """2.5 — rests did not exist; only policy config strings mentioned them."""

    def test_short_rest_heals(self, manager):
        manager.award_xp("aggi", 6500)
        c = manager.characters["aggi"]
        c.hit_points["current"] = 5
        assert manager.short_rest("aggi", 2)["healed"] > 0

    def test_short_rest_spends_hit_dice(self, manager):
        manager.award_xp("aggi", 6500)  # level 5 -> 5 hit dice
        result = manager.short_rest("aggi", 2)
        assert result["hit_dice_spent"] == 2
        assert result["hit_dice_remaining"] == 3

    def test_short_rest_cannot_overspend_dice(self, manager):
        result = manager.short_rest("aggi", 99)
        assert result["hit_dice_spent"] <= manager.characters["aggi"].level

    def test_short_rest_never_exceeds_max_hp(self, manager):
        manager.award_xp("aggi", 6500)
        c = manager.characters["aggi"]
        c.hit_points["current"] = c.hit_points["maximum"] - 1
        manager.short_rest("aggi", 5)
        assert c.hit_points["current"] == c.hit_points["maximum"]

    def test_long_rest_restores_full_hp(self, manager):
        c = manager.characters["aggi"]
        c.hit_points["current"] = 1
        assert manager.long_rest("aggi")["hit_points"]["current"] == c.hit_points["maximum"]

    def test_long_rest_returns_half_hit_dice(self, manager):
        manager.award_xp("aggi", 6500)  # level 5
        c = manager.characters["aggi"]
        c.hit_dice_remaining = 0
        assert manager.long_rest("aggi")["hit_dice_remaining"] == 2

    def test_long_rest_refills_stormlight(self, manager):
        manager.award_xp("aggi", 6500)
        c = manager.characters["aggi"]
        c.stormlight_current = 0
        assert manager.long_rest("aggi")["stormlight_current"] == c.stormlight_capacity

    def test_long_rest_clears_temporary_hp(self, manager):
        manager.characters["aggi"].hit_points["temporary"] = 5
        manager.long_rest("aggi")
        assert manager.characters["aggi"].hit_points["temporary"] == 0

    def test_party_rest_covers_everyone(self, manager):
        manager.add_character({
            "character_id": "kali", "name": "Kali", "level": 1,
            "ability_scores": {"strength": 10, "dexterity": 14, "constitution": 12,
                               "intelligence": 12, "wisdom": 12, "charisma": 14},
            "hit_points": {"current": 1, "maximum": 10, "temporary": 0},
            "armor_class": 12, "character_class": "Lightweaver",
            "race": "Azish", "background": "Hermit",
        })
        results = manager.rest_party(long=True)
        assert set(results) == {"aggi", "kali"}
        assert manager.characters["kali"].hit_points["current"] == 10


class TestDeathSaves:
    """
    2.5 — PolicyEngine declares a death_saves policy and NOTHING consumed it.
    Combat treated hp<=0 as instantly out, so dropping equalled dying.
    """

    @pytest.fixture
    def dying(self, manager):
        manager.characters["aggi"].hit_points["current"] = 0
        return manager

    def test_three_failures_kill(self, dying):
        for _ in range(3):
            result = dying.roll_death_save("aggi", roll=5)
        assert result["dead"] is True
        assert dying.characters["aggi"].is_dead is True

    def test_three_successes_stabilise(self, dying):
        for _ in range(3):
            result = dying.roll_death_save("aggi", roll=15)
        assert result["stable"] is True
        assert dying.characters["aggi"].is_dead is False

    def test_natural_20_revives_at_1_hp(self, dying):
        assert dying.roll_death_save("aggi", roll=20)["revived"] is True
        assert dying.characters["aggi"].hit_points["current"] == 1

    def test_natural_1_counts_double(self, dying):
        assert dying.roll_death_save("aggi", roll=1)["failures"] == 2

    def test_dc_10_boundary(self, dying):
        assert dying.roll_death_save("aggi", roll=10)["successes"] == 1
        assert dying.roll_death_save("aggi", roll=9)["failures"] == 1

    def test_conscious_characters_do_not_roll(self, manager):
        assert "skipped" in manager.roll_death_save("aggi")

    def test_stabilised_characters_stop_rolling(self, dying):
        dying.stabilize("aggi")
        assert "stable" in dying.roll_death_save("aggi", roll=5)

    def test_long_rest_clears_death_saves(self, dying):
        dying.roll_death_save("aggi", roll=5)
        dying.long_rest("aggi")
        assert dying.characters["aggi"].death_save_failures == 0

    def test_dropping_is_not_dying(self, dying):
        """The whole point: 0 HP must not equal dead."""
        assert dying.characters["aggi"].is_dead is False
        dying.roll_death_save("aggi", roll=15)
        assert dying.characters["aggi"].is_dead is False


# ------------------------------------------------- 2.6 travel, world, game clock

class TestWorldGraphAndTravel:
    """
    2.6 — `exits`, `hazards` and `npcs_present` were declared in
    LocationContext and NEVER written, and no travel verb existed, so the party
    could not go anywhere. Shards of Honor's three-artifact structure (D6) was
    unreachable.
    """

    @pytest.fixture
    def world(self):
        ge = GameEngine()
        ge.register_location("Kholinar", "A shattered city", ["walls"],
                             exits=["Urithiru"], hazards=["patrols"])
        ge.register_location("Urithiru", "The tower city", ["oathgate"],
                             exits=["Kholinar"])
        ge.set_location("Kholinar", description="A shattered city",
                        features=["walls"])
        return ge

    def test_locations_are_registered(self, world):
        graph = world.game_state.location_context["known_locations"]
        assert {"Kholinar", "Urithiru"} <= set(graph)

    def test_exits_are_reported(self, world):
        assert world.get_available_exits() == ["Urithiru"]

    def test_travel_moves_the_party(self, world):
        result = world.travel_to("Urithiru")
        assert result["success"] is True
        assert world.game_state.location_context["current_location"] == "Urithiru"

    def test_travel_is_case_insensitive(self, world):
        assert world.travel_to("URITHIRU")["success"] is True

    def test_partial_names_match_on_whole_words(self, world):
        """A naive substring test matched 'A' inside 'Shattered Plains'."""
        assert world.travel_to("the tower of Urithiru")["success"] is True

    def test_unknown_destination_is_discovered(self, world):
        result = world.travel_to("Shattered Plains")
        assert result["success"] is True, "the DM must be able to invent places"
        assert "Shattered Plains" in world.game_state.location_context["known_locations"]

    def test_unreachable_location_is_refused(self):
        ge = GameEngine()
        ge.register_location("A", exits=["B"])
        ge.register_location("B", exits=["A"])
        ge.register_location("Isolated Fortress", exits=[])
        ge.set_location("A")
        assert ge.travel_to("Isolated Fortress")["success"] is False

    def test_hazards_follow_the_location(self, world):
        world.travel_to("Urithiru")
        world.travel_to("Kholinar")
        assert world.game_state.location_context["hazards"] == ["patrols"]

    def test_set_location_no_longer_wipes_description(self, world):
        """
        description/features defaulted to ""/[] , so set_location(name) — what
        state_changes.location does — erased the current location's details.
        """
        before = world.game_state.location_context["description"]
        world.set_location("Kholinar")
        assert world.game_state.location_context["description"] == before

    def test_travel_advances_the_clock(self, world):
        before = world.get_game_time()["elapsed_hours"]
        world.travel_to("Urithiru")
        assert world.get_game_time()["elapsed_hours"] > before


class TestGameClockAndHighstorms:
    """
    2.6 — there was no clock and no day counter. update_environment() had ZERO
    callers so weather never changed, and the campaign's own
    'WEATHER: Highstorm-approaching' was parsed and dropped.
    """

    def test_time_starts_on_day_one(self, engine):
        assert engine.get_game_time()["day"] == 1

    def test_hours_accumulate_into_days(self, engine):
        engine.advance_time(hours=30)
        assert engine.get_game_time()["day"] == 2

    def test_part_of_day_tracks_the_hour(self, engine):
        engine.advance_time(hours=14)  # 14:00
        assert engine.get_game_time()["part_of_day"] == "afternoon"

    def test_lighting_follows_the_clock(self, engine):
        engine.advance_time(hours=2)  # 02:00
        assert engine.game_state.environment["lighting"] == "dark"

    def test_highstorm_arrives_on_schedule(self, engine):
        """The counter used to jump 1 -> 5, so 'highstorm' never occurred."""
        seen = set()
        for _ in range(6):
            seen.add(engine.advance_time(days=1)["weather"])
        assert "highstorm" in seen, f"never stormed: {seen}"

    def test_weather_escalates_toward_the_storm(self, engine):
        weather = [engine.advance_time(days=1)["weather"] for _ in range(6)]
        assert "highstorm-approaching" in weather
        assert "highstorm-imminent" in weather

    def test_cycle_repeats(self, engine):
        storms = sum(engine.advance_time(days=1)["weather"] == "highstorm"
                     for _ in range(12))
        assert storms >= 2, "highstorms should recur"

    def test_days_until_storm_is_never_negative(self, engine):
        for _ in range(20):
            assert engine.advance_time(days=1)["days_until_highstorm"] >= 0


# --------------------------------------------- 2.9 Tier-2 Cosmere rules (grounded)

from components.cosmere_rules import CosmereRules


class TestCosmereRulesAreGrounded:
    """
    2.9 — before this, every Cosmere "rule" in the codebase was hand-written
    Python authored from general knowledge, not from the Handbook. The costs
    (Lashing 1 sphere, Soulcast 3 spheres) were plausible and WRONG: the
    Handbook uses an expendable DICE economy recovered on rest, not per-use
    spheres. That is exactly the failure mode D5 exists to prevent.
    """

    @pytest.fixture
    def rules(self):
        return CosmereRules()

    def test_rules_load(self, rules):
        assert len(rules.maneuvers()) > 0, "no Tier-2 rules loaded"

    def test_every_reviewed_quote_matches_the_handbook(self, rules):
        """The whole point: claims must be checkable against the source."""
        result = rules.verify_citations()
        assert result["checked"] > 0, "nothing was citation-checked"
        assert not result["mismatched"], (
            f"{len(result['mismatched'])} citation(s) no longer match the "
            f"Handbook: {result['mismatched'][:3]}"
        )

    def test_unreviewed_entries_cannot_adjudicate(self, rules):
        """D5: an unreviewed rule is confidently wrong and must be excluded."""
        assert all(rules._reviewed(m) for m in rules.maneuvers())
        assert all(rules._reviewed(f) for f in rules.features())

    def test_unreviewed_entries_are_still_visible(self, rules):
        """They are the extraction backlog, not something to hide."""
        assert isinstance(rules.unreviewed(), list)

    def test_lashing_dice_economy_not_spheres(self, rules):
        """The correction: Windrunners spend DICE, not Stormlight per use."""
        economy = rules.economy_for_order("Windrunner")
        assert economy["name"] == "Lashing Dice"
        assert economy["starting_dice"] == 2
        assert economy["starting_die_size"] == 4
        assert "rest" in economy["recovery"]

    def test_investiture_point_costs_match_the_table(self, rules):
        """Quoted table: 1st=2, 2nd=3, 3rd=5, 4th=6, 5th=7."""
        assert [rules.investiture_cost(n) for n in (1, 2, 3, 4, 5)] == [2, 3, 5, 6, 7]

    def test_cantrips_are_free(self, rules):
        assert rules.investiture_cost(0) == 0

    def test_elsecaller_always_spends_one(self, rules):
        assert rules.investiture_cost(5, order="Elsecaller") == 1

    def test_invested_save_dc_formula(self, rules):
        assert rules.invested_save_dc(3, 4) == 15  # 8 + 3 + 4

    def test_long_rest_stormlight_requirement(self, rules):
        assert rules.stormlight_for_long_rest(5) == 25  # level x 5

    def test_orders_have_their_real_surges(self, rules):
        assert rules.surges_for_order("Windrunner") == ["Adhesion", "Gravitation"]
        assert rules.surges_for_order("Lightweaver") == ["Illumination", "Transformation"]

    def test_maneuvers_are_filtered_by_order(self, rules):
        names = [m["name"] for m in rules.maneuvers(order="Windrunner")]
        assert "Full Lashing" in names
        assert all("Windrunner" in m["orders"]
                   for m in rules.maneuvers(order="Windrunner"))

    def test_maneuver_lookup_by_id_and_name(self, rules):
        assert rules.get_maneuver("full_lashing") is not None
        assert rules.get_maneuver("Full Lashing") is not None
        assert rules.get_maneuver("nonexistent") is None

    def test_maneuvers_carry_automation_trees(self, rules):
        """Avrae-style declarative effects (§8 / 3.1), not bespoke Python."""
        full_lashing = rules.get_maneuver("full_lashing")
        assert full_lashing["automation"], "no automation tree"
        assert full_lashing["automation"][0]["type"] == "target"

    def test_prompt_summary_is_usable(self, rules):
        summary = rules.describe_for_prompt("Windrunner")
        assert "Adhesion" in summary
        assert "Lashing Dice" in summary
        assert "Full Lashing" in summary

    def test_unknown_order_degrades(self, rules):
        assert rules.order("Notanorder") is None
        assert rules.surges_for_order("Notanorder") == []
        assert rules.describe_for_prompt("Notanorder") == ""


# ---------------------------------------------------- 2.9 Tier-1 SRD (vendored)

from components.srd_rules import SRDRules


class TestSRDRulesTier1:
    """
    2.9 Tier 1 — SRD 5e as structured JSON, vendored from 5e-bits/5e-database
    (MIT; data under OGL 1.0a). RAG-over-PDFs is the wrong tool for RULES: a
    retrieved chunk saying "goblins are weak but cunning" is prose the LLM must
    interpret, reintroducing the hallucination we are engineering out. These
    records carry fields code can compute with.
    """

    @pytest.fixture
    def srd(self):
        return SRDRules()

    def test_data_is_vendored(self, srd):
        available = srd.available()
        assert available.get("monsters", 0) > 300, (
            "SRD data missing — run scripts/vendor_srd_data.py"
        )
        assert available.get("spells", 0) > 300

    def test_monster_lookup_is_exact(self, srd):
        assert srd.monster("Goblin")["name"] == "Goblin"

    def test_monster_stats_are_adjudicable(self, srd):
        """The point: numbers, not prose."""
        goblin = srd.monster_stats("Goblin")
        assert goblin["armor_class"] == 15
        assert goblin["hit_points"]["maximum"] == 7
        assert goblin["challenge_rating"] == 0.25
        assert goblin["hit_dice"] == "2d6"

    def test_monster_attacks_carry_real_numbers(self, srd):
        attack = srd.monster_stats("Goblin")["attacks"][0]
        assert attack["name"] == "Scimitar"
        assert attack["attack_bonus"] == 4
        assert attack["damage_dice"] == "1d6+2"
        assert attack["damage_type"] == "slashing"

    def test_monster_ability_scores_are_real(self, srd):
        """Not all 10s — the AbilityConfig bug made every entity flat."""
        scores = srd.monster_stats("Goblin")["ability_scores"]
        assert scores["dexterity"] == 14
        assert scores["strength"] == 8
        assert len(set(scores.values())) > 1

    def test_stats_shape_matches_npc_generator_output(self, srd):
        """So an SRD monster can substitute for an LLM-generated statblock."""
        goblin = srd.monster_stats("Goblin")
        for key in ("name", "armor_class", "hit_points", "ability_scores",
                    "attacks", "character_class", "race"):
            assert key in goblin, f"missing {key} — cannot feed CharacterManager"

    def test_partial_names_match_whole_words(self, srd):
        assert srd.monster_stats("goblin warrior")["name"] == "Goblin"

    def test_naive_substring_does_not_match(self, srd):
        """Guard the 2.6 bug class: single letters must not match."""
        assert srd.monster("a") is None

    def test_encounter_building_by_cr(self, srd):
        low = srd.monsters_by_cr(0, 1)
        assert len(low) > 50
        assert "Goblin" in low
        assert "Adult Red Dragon" not in low

    def test_weapon_damage_from_the_srd(self, srd):
        """Supersedes the _WEAPON_STATS table I authored from memory (1.4)."""
        assert srd.weapon_damage("Longsword")["damage_dice"] == "1d8"
        assert srd.weapon_damage("Greatsword")["damage_dice"] == "2d6"
        assert srd.weapon_damage("Dagger")["damage_dice"] == "1d4"

    def test_hand_written_weapon_table_agrees_with_the_srd(self, srd):
        """
        My 1.4 table was authored from general knowledge. Confirm it against the
        real data — and prefer the SRD when they disagree.
        """
        from components.dnd_engine_wrapper import DnDEngineWrapper

        for name in ("Longsword", "Greatsword", "Dagger", "Rapier", "Warhammer"):
            srd_dice = srd.weapon_damage(name)["damage_dice"]
            hand = DnDEngineWrapper._WEAPON_STATS[name.lower()]
            assert srd_dice.startswith(f"{hand[0]}d{hand[1]}"), (
                f"{name}: hand-written {hand[0]}d{hand[1]} != SRD {srd_dice}"
            )

    def test_conditions_carry_rules_text(self, srd):
        prone = srd.condition("Prone")
        assert prone["name"] == "Prone"
        assert prone.get("desc"), "condition has no rules text"

    def test_spell_lookup(self, srd):
        fireball = srd.spell("Fireball")
        assert fireball["level"] == 3
        assert "8d6" in str(fireball.get("damage", {}))

    def test_unknown_lookups_return_none(self, srd):
        assert srd.monster("Sligtinvented Beast") is None
        assert srd.spell("Nonexistent Cantrip") is None
        assert srd.weapon_damage("Frying Pan") is None

    def test_missing_data_directory_degrades(self, tmp_path):
        empty = SRDRules(srd_dir=tmp_path / "nope")
        assert empty.available() == {}
        assert empty.monster("Goblin") is None


# ------------------------------------------- 2.10/2.11 rules backlog + gap tracker

from components.rules_gap_tracker import (
    RulesGapTracker, TIER_CANONICAL, TIER_COMPOSED, TIER_JUDGED, TIER_NARRATIVE,
)


class TestExtractionBacklogIsClear:
    """
    2.10 — the seven orders that shipped as reviewed:false have now been read
    from the Handbook and verified, so nothing is adjudicating on guesswork.
    """

    @pytest.fixture
    def rules(self):
        return CosmereRules()

    def test_no_unreviewed_entries_remain(self, rules):
        assert rules.unreviewed() == [], (
            f"still guessing at: {[u.get('name') for u in rules.unreviewed()]}"
        )

    def test_all_citations_verify(self, rules):
        result = rules.verify_citations()
        assert result["checked"] >= 20
        assert not result["mismatched"]

    def test_dustbringer_correction(self, rules):
        """
        My initial guess was Division+Abrasion. The Handbook says Abrasion first,
        with Division only from 5th level — extraction caught the error.
        """
        assert rules.surges_for_order("Dustbringer") == ["Abrasion", "Division"]
        assert "5th level" in rules.order("Dustbringer").get("notes", "")

    def test_bondsmith_is_not_playable(self, rules):
        """
        Also caught by extraction: Bondsmith is in a separate supplement, so
        there are NINE playable orders, not ten.
        """
        assert rules.order("Bondsmith").get("playable") is False

    def test_every_playable_order_has_two_surges(self, rules):
        for name in ("Windrunner", "Skybreaker", "Dustbringer", "Edgedancer",
                     "Truthwatcher", "Lightweaver", "Elsecaller", "Willshaper",
                     "Stoneward"):
            assert len(rules.surges_for_order(name)) == 2, f"{name} surges wrong"

    def test_spren_bonds_are_recorded(self, rules):
        assert rules.order("Lightweaver")["spren"] == "Cryptic"
        assert rules.order("Edgedancer")["spren"] == "cultivationspren"


class TestRulesGapTracker:
    """
    2.11 — the answer to "extraction will miss rules": it will, and the system
    must say WHICH. Recurring fallbacks rank themselves into a work queue.
    """

    @pytest.fixture
    def tracker(self, tmp_path):
        return RulesGapTracker(store_path=tmp_path / "gaps.json")

    def test_canonical_adjudications_are_not_gaps(self, tracker):
        assert tracker.record("attack with a sword", TIER_CANONICAL) == {}
        assert tracker.record("dash", TIER_COMPOSED) == {}
        assert tracker.stats()["distinct_gaps"] == 0

    def test_judged_rulings_are_recorded(self, tracker):
        tracker.record("Lash a boulder onto the Fused", TIER_JUDGED)
        assert tracker.stats()["distinct_gaps"] == 1

    def test_narrative_fallbacks_are_recorded(self, tracker):
        tracker.record("admire the scenery", TIER_NARRATIVE)
        assert tracker.stats()["by_tier"]["narrative"] == 1

    def test_phrasings_are_deduplicated(self, tracker):
        tracker.record("Lash the boulder onto the Fused", TIER_JUDGED)
        entry = tracker.record("lash the boulder onto the fused!", TIER_JUDGED)
        assert entry["uses"] == 2, "punctuation/case should not create a new gap"

    def test_backlog_ignores_one_off_noise(self, tracker):
        tracker.record("something bizarre and unique", TIER_JUDGED)
        assert tracker.backlog() == [], "a single occurrence is probably noise"

    def test_backlog_surfaces_recurring_gaps(self, tracker):
        for _ in range(3):
            tracker.record("Soulcast the wall", TIER_JUDGED)
        assert len(tracker.backlog()) == 1

    def test_backlog_is_ranked_by_frequency(self, tracker):
        for _ in range(5):
            tracker.record("frequent gap", TIER_JUDGED)
        for _ in range(2):
            tracker.record("rarer gap", TIER_JUDGED)
        backlog = tracker.backlog()
        assert backlog[0]["situation"] == "frequent gap"

    def test_rulings_and_citations_are_kept(self, tracker):
        entry = tracker.record("Lash a boulder", TIER_JUDGED,
                               ruling="treat as improvised weapon",
                               citations=["handbook#p47"])
        assert entry["rulings"][0]["citations"] == ["handbook#p47"]

    def test_ruling_history_is_bounded(self, tracker):
        for i in range(20):
            tracker.record("recurring", TIER_JUDGED, ruling=f"ruling {i}")
        entry = tracker.backlog()[0]
        assert len(entry["rulings"]) <= 5

    def test_promotion_clears_the_gap(self, tracker):
        for _ in range(3):
            tracker.record("Soulcast the wall", TIER_JUDGED)
        assert tracker.mark_promoted("Soulcast the wall") is True
        assert tracker.backlog() == []

    def test_promotion_of_unknown_gap_is_false(self, tracker):
        assert tracker.mark_promoted("never happened") is False

    def test_gaps_persist_across_sessions(self, tmp_path):
        path = tmp_path / "gaps.json"
        first = RulesGapTracker(store_path=path)
        for _ in range(3):
            first.record("Lash a boulder", TIER_JUDGED)
        second = RulesGapTracker(store_path=path)
        assert second.backlog()[0]["uses"] == 3

    def test_report_is_readable(self, tracker):
        for _ in range(3):
            tracker.record("Soulcast the wall", TIER_JUDGED)
        report = tracker.report()
        assert "Rules gap report" in report
        assert "Soulcast the wall" in report

    def test_report_says_so_when_clean(self, tracker):
        assert "canonical rules" in tracker.report()

    def test_corrupt_store_degrades(self, tmp_path):
        path = tmp_path / "gaps.json"
        path.write_text("{not json")
        assert RulesGapTracker(store_path=path).stats()["distinct_gaps"] == 0


# ------------------------------------- 2.12/2.13 campaign schema + endgame (D2)

from components.campaign_schema import CampaignSchema, EndgameEvaluator

CAMPAIGN = "data/current_campaign/shards_of_honor.json"


class TestCampaignSchema:
    """
    2.12 — the campaign was all prose (main_plot, hooks, rewards) with no
    endgame condition, no acts, and quests as bare title strings, so detecting
    "the campaign is over" was impossible.
    """

    @pytest.fixture
    def campaign(self, engine):
        return CampaignSchema(CAMPAIGN, game_engine=engine)

    def test_campaign_is_structured(self, campaign):
        assert campaign.has_structure(), "campaign still prose-only"

    def test_quests_are_objects_not_strings(self, campaign):
        quests = campaign.quests()
        assert len(quests) >= 6
        for q in quests:
            assert {"id", "title", "objectives", "prereqs", "status"} <= set(q)

    def test_acts_match_the_five_session_structure(self, campaign):
        assert len(campaign.acts()) == 3
        sessions = [s for act in campaign.acts() for s in act["sessions"]]
        assert sorted(sessions) == [1, 2, 3, 4, 5]

    def test_quest_lookup_by_id_and_title(self, campaign):
        assert campaign.quest("artifact_1") is not None
        assert campaign.quest("Recover the first ancient artifact") is not None
        assert campaign.quest("nonexistent") is None

    def test_prereqs_gate_availability(self, campaign):
        """Only the opening quest should be available at session 1."""
        assert [q["id"] for q in campaign.available_quests()] == ["first_oath"]

    def test_legacy_string_quests_still_load(self, tmp_path, engine):
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps({"title": "Old", "quests": ["Find the sword"]}))
        legacy = CampaignSchema(path, game_engine=engine)
        assert legacy.quests()[0]["title"] == "Find the sword"
        assert legacy.has_structure() is False, "no endgame -> not structured"


class TestEndgameDetection:
    """
    2.13 / D2 — closure is AUTHORED and code-detected. The LLM narrates the
    ending; it does not decide when the story is over.
    """

    @pytest.fixture
    def campaign(self, engine):
        return CampaignSchema(CAMPAIGN, game_engine=engine)

    def _complete(self, engine, title):
        engine.add_quest_objective(title)
        engine.complete_quest_objective(title)

    def test_not_complete_at_the_start(self, campaign):
        assert campaign.is_complete() is False

    def test_three_artifacts_alone_do_not_end_it(self, campaign, engine):
        for n in ("first", "second", "third"):
            self._complete(engine, f"Recover the {n} ancient artifact")
        assert campaign.is_complete() is False, "the ritual must still be stopped"

    def test_full_condition_ends_the_campaign(self, campaign, engine):
        for n in ("first", "second", "third"):
            self._complete(engine, f"Recover the {n} ancient artifact")
        self._complete(engine, "Stop Odium's ritual on the battlefield")
        assert campaign.is_complete() is True

    def test_progress_climbs(self, campaign, engine):
        assert campaign.endgame_progress()["percent"] == 0
        for n in ("first", "second", "third"):
            self._complete(engine, f"Recover the {n} ancient artifact")
        assert campaign.endgame_progress()["percent"] == 50
        self._complete(engine, "Stop Odium's ritual on the battlefield")
        assert campaign.endgame_progress()["percent"] == 100

    def test_closing_narration_is_authored(self, campaign):
        narration = campaign.closing_narration()
        assert len(narration) > 100
        assert "ritual" in narration.lower()

    def test_failure_condition_can_fire(self, campaign, engine):
        engine.set_campaign_flag("barrier_shattered", True)
        condition = campaign.data["endgame"]["failure_condition"]
        assert EndgameEvaluator(engine).evaluate(condition) is True


class TestEndgamePredicates:
    """The condition language must be reliable — it decides when play stops."""

    @pytest.fixture
    def ev(self, engine):
        return EndgameEvaluator(engine, quest_index={"artifact_1": "Get the sword"})

    def test_flag_predicate(self, ev, engine):
        assert ev.check_predicate("flag:ritual_stopped") is False
        engine.set_campaign_flag("ritual_stopped", True)
        assert ev.check_predicate("flag:ritual_stopped") is True

    def test_falsy_flag_is_not_satisfied(self, ev, engine):
        engine.set_campaign_flag("ritual_stopped", False)
        assert ev.check_predicate("flag:ritual_stopped") is False

    def test_quest_id_resolves_to_its_title(self, ev, engine):
        """Conditions use stable IDs; the engine stores titles."""
        engine.add_quest_objective("Get the sword")
        engine.complete_quest_objective("Get the sword")
        assert ev.check_predicate("quest:artifact_1") is True

    def test_ideal_predicate(self, ev, engine):
        assert ev.check_predicate("ideal:2") is False
        engine.character_manager.characters["aggi"].ideal_level = 3
        assert ev.check_predicate("ideal:2") is True

    def test_location_predicate(self, ev, engine):
        engine.register_location("Urithiru", exits=[])
        assert ev.check_predicate("location:Urithiru") is False
        engine.travel_to("Urithiru")
        assert ev.check_predicate("location:Urithiru") is True

    def test_all_of(self, ev, engine):
        engine.set_campaign_flag("a", True)
        assert ev.evaluate({"all_of": ["flag:a", "flag:b"]}) is False
        engine.set_campaign_flag("b", True)
        assert ev.evaluate({"all_of": ["flag:a", "flag:b"]}) is True

    def test_any_of(self, ev, engine):
        assert ev.evaluate({"any_of": ["flag:a", "flag:b"]}) is False
        engine.set_campaign_flag("b", True)
        assert ev.evaluate({"any_of": ["flag:a", "flag:b"]}) is True

    def test_none_of(self, ev, engine):
        assert ev.evaluate({"none_of": ["flag:doom"]}) is True
        engine.set_campaign_flag("doom", True)
        assert ev.evaluate({"none_of": ["flag:doom"]}) is False

    def test_wildcards_match(self, ev, engine):
        engine.set_campaign_flag("artifact_two_found", True)
        assert ev.check_predicate("flag:artifact_*") is True

    def test_malformed_predicates_return_false(self, ev):
        for junk in ("", "nocolon", "unknownkind:x", None):
            assert ev.check_predicate(junk) is False

    def test_unevaluatable_condition_returns_false(self, ev):
        assert ev.evaluate({"nonsense": True}) is False
        assert ev.evaluate(None) is False

    def test_missing_engine_degrades(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({"quests": [], "endgame": {"condition": "flag:x"}}))
        assert CampaignSchema(path, game_engine=None).is_complete() is False


class TestGeneratorEmitsStructure:
    """
    2.14 — teach campaign_generator the new schema, or every generated campaign
    needs hand-migration like shards_of_honor did.
    """

    def _prompt_source(self):
        import inspect
        from generators.campaign_generator import CampaignGenerator
        return inspect.getsource(CampaignGenerator.generate_campaign)

    def test_prompt_requires_structured_quests(self):
        src = self._prompt_source()
        assert '"quests"' in src
        assert "prereqs" in src
        assert "snake_case" in src, "quest ids must be stable for endgame refs"

    def test_prompt_requires_an_endgame_condition(self):
        src = self._prompt_source()
        assert '"endgame"' in src
        assert "condition" in src
        assert "closing_narration" in src

    def test_prompt_documents_the_predicate_language(self):
        src = self._prompt_source()
        for token in ("quest:", "flag:", "all_of", "any_of", "count"):
            assert token in src, f"predicate form {token!r} not documented"

    def test_prompt_requires_acts(self):
        assert '"acts"' in self._prompt_source()

    def test_prompt_states_the_dm_does_not_decide_the_ending(self):
        """D2: closure is authored and code-detected."""
        src = self._prompt_source()
        assert "never decides" in src or "DETECTS" in src

    def test_generator_is_importable(self):
        """
        campaign_generator imported agents/haystack_pipeline_agent.py, which does
        NOT exist — so the module was unimportable and D1's `dnd_reference`
        collection had no working consumer at all.
        """
        from generators.campaign_generator import CampaignGenerator
        assert CampaignGenerator is not None

    def test_generator_reads_the_reference_collection(self):
        """D1: structural few-shots come from dnd_reference, not dnd_documents."""
        import inspect
        from generators.campaign_generator import CampaignGenerator
        src = inspect.getsource(CampaignGenerator._init_direct_retriever)
        assert "dnd_reference" in src or "collection_name" in src


# ------------------------------------------- 1.9 / 2.15 / 2.16 party support (D3)

class TestPartyRoster:
    """
    2.15 — D3 commits to N-player parties. Single-PC play must be a
    CONFIGURATION of the party path, never a separate code path.
    """

    @pytest.fixture
    def party_game(self, engine):
        for cid, name in (("aggi", "Aggi"), ("kali", "Kali")):
            if cid not in engine.character_manager.characters:
                engine.add_character({
                    "character_id": cid, "name": name, "level": 3,
                    "ability_scores": {"strength": 12, "dexterity": 14,
                                       "constitution": 12, "intelligence": 12,
                                       "wisdom": 12, "charisma": 14},
                    "hit_points": {"current": 18, "maximum": 24, "temporary": 0},
                    "armor_class": 13, "character_class": "Lightweaver",
                    "race": "Alethi", "background": "Soldier",
                    "radiant_order": "Lightweaver",
                    "stormlight_current": 4, "stormlight_capacity": 6,
                })
        g = HaystackDnDGame.__new__(HaystackDnDGame)
        g.game_engine = engine
        g.character_manager = engine.character_manager
        g.dnd_engine_wrapper = None
        g.current_choices = []
        return g

    def test_party_lists_every_pc(self, party_game):
        assert {"aggi", "kali"} <= set(party_game._party_ids())

    def test_npcs_are_excluded_from_the_party(self, party_game):
        party_game.character_manager.add_npc({
            "name": "Goblin", "level": 1,
            "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                               "intelligence": 10, "wisdom": 8, "charisma": 8},
            "hit_points": {"current": 7, "maximum": 7, "temporary": 0},
            "armor_class": 15, "character_class": "Goblin",
            "race": "Goblin", "background": "Raider",
        })
        assert not any("goblin" in cid for cid in party_game._party_ids())

    def test_active_defaults_to_the_first_member(self, party_game):
        assert party_game._active_character_id() == party_game._party_ids()[0]

    def test_switch_by_roster_number(self, party_game):
        second = party_game._party_ids()[1]
        assert party_game._switch_character("2") is True
        assert party_game._active_character_id() == second

    def test_switch_by_name(self, party_game):
        assert party_game._switch_character("Kali") is True
        assert party_game._active_character_id() == "kali"

    def test_switch_to_unknown_is_refused(self, party_game):
        before = party_game._active_character_id()
        assert party_game._switch_character("Nobody") is False
        assert party_game._active_character_id() == before

    def test_out_of_range_switch_is_refused(self, party_game):
        assert party_game._switch_character("99") is False

    def test_skill_check_uses_the_active_character(self, party_game):
        """Switching must actually change who rolls."""
        party_game._switch_character("Kali")
        party_game.current_choices = [
            {"title": "Sneak", "description": "x", "suggested_dc": 13,
             "skill_hints": ["stealth"]},
        ]
        result = party_game._process_input("1")
        assert result["skill_check_result"]["actor"] == "kali"

    def test_roster_renders(self, party_game, capsys):
        party_game._show_party()
        out = capsys.readouterr().out
        assert "Aggi" in out and "Kali" in out
        assert "▶" in out, "the acting character must be marked"

    def test_turn_loop_exposes_party_commands(self):
        import inspect
        src = inspect.getsource(HaystackDnDGame.run_interactive)
        for command in ('"party"', "switch", '"rest"'):
            assert command in src, f"{command} not wired into the turn loop"


class TestPartyStatePersists:
    """
    2.16 — XP, rests and loot are party-wide, and the whole roster must
    round-trip. Progression fields were being silently dropped on load.
    """

    @pytest.fixture
    def manager(self):
        m = CharacterManager()
        for cid, name in (("aggi", "Aggi"), ("kali", "Kali")):
            m.add_character({
                "character_id": cid, "name": name, "level": 1,
                "ability_scores": {"strength": 12, "dexterity": 14,
                                   "constitution": 14, "intelligence": 10,
                                   "wisdom": 10, "charisma": 14},
                "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
                "armor_class": 13, "character_class": "Lightweaver",
                "race": "Alethi", "background": "Soldier",
                "radiant_order": "Lightweaver",
            })
        return m

    def _round_trip(self, manager):
        state = {cid: c.to_dict() for cid, c in manager.characters.items()}
        restored = CharacterManager()
        for cid, sheet in state.items():
            sheet.setdefault("character_id", cid)
            restored.add_character(sheet)
        return restored

    def test_whole_party_round_trips(self, manager):
        assert set(self._round_trip(manager).characters) == {"aggi", "kali"}

    def test_xp_survives_a_save(self, manager):
        """XP reset to 0 on load — add_character ignored the 2.5 fields."""
        manager.award_xp("aggi", 2700)
        assert self._round_trip(manager).characters["aggi"].experience_points == 2700

    def test_level_survives_a_save(self, manager):
        manager.award_xp("aggi", 2700)
        assert self._round_trip(manager).characters["aggi"].level == 4

    def test_hit_dice_survive_a_save(self, manager):
        manager.characters["aggi"].hit_dice_remaining = 2
        assert self._round_trip(manager).characters["aggi"].hit_dice_remaining == 2

    def test_death_save_progress_survives(self, manager):
        manager.characters["aggi"].death_save_failures = 2
        assert self._round_trip(manager).characters["aggi"].death_save_failures == 2

    def test_stormlight_survives_a_save(self, manager):
        manager.award_xp("aggi", 2700)
        manager.characters["aggi"].stormlight_current = 5
        restored = self._round_trip(manager).characters["aggi"]
        assert restored.stormlight_current == 5
        assert restored.stormlight_capacity > 0

    def test_rest_applies_to_everyone(self, manager):
        for c in manager.characters.values():
            c.hit_points["current"] = 1
        manager.rest_party(long=True)
        assert all(c.hit_points["current"] == c.hit_points["maximum"]
                   for c in manager.characters.values())


class TestCombatReceivesTheWholeParty:
    """1.9 — two lines collapsed the game to a single PC in combat."""

    def test_orchestrator_passes_a_list(self):
        import inspect
        from orchestrator.pipeline_integration import PipelineOrchestrator
        src = inspect.getsource(PipelineOrchestrator._run_combat_pipeline)
        assert "player_character_ids" in src, "still narrowing to one PC"

    def test_combat_agent_forwards_the_list(self):
        import inspect
        from agents.combat_agent import CombatAgent
        src = inspect.getsource(CombatAgent.run)
        assert "player_character_ids=player_char_ids" in src
        assert "player_character_ids=[player_char_id]" not in src

    def test_initializer_signature_is_party_shaped(self):
        import inspect
        from components.combat.combat_initializer import CombatInitializer
        params = inspect.signature(CombatInitializer.initialize_combat).parameters
        assert "player_character_ids" in params
