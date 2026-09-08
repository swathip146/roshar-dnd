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
        import agents.npc_controller_agent as mod
        import inspect

        src = inspect.getsource(mod.create_npc_controller_agent)
        assert "YOU WRITE THE WORDS" in src


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
