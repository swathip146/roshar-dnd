"""
A resolved combat must reach the player — and record the turn.

A live 3-turn run resolved combat correctly (`outcome=defeat, rounds=4`), applied
damage, and marked the campaign ended. The player was then told:

    "The world seems momentarily confused by your action. Try something else..."

and the log said `Processing failed: Unknown error`.

The cause was purely structural: `play_turn()` gates on
`response_dict["success"]`, and `CombatAgent` returns only
`{"response": {...}}` — no `success` key anywhere. So every combat turn was
classified as a failure. Two consequences beyond the wrong message:

  * The narrative beat for the turn was never recorded, because
    `process_scenario_state_updates()` is only reached on the success path. A live
    run showed ZERO beats while 2.2 was working correctly.
  * `_handle_unknown` then assigned the nested DICT to `formatted_response`,
    which is how "The adventure continues" reached the player.

These tests assert on the shape the game loop actually reads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]


class _StubAgent:
    """CombatAgent's real return shape."""

    def __init__(self, outcome="defeat", rounds=4, narrative="The fight ends."):
        self.payload = {"response_type": "combat_complete", "outcome": outcome,
                        "rounds": rounds, "narrative": narrative,
                        "combat_log": []}

    def run(self, dto):
        return {"response": dict(self.payload)}


def _orchestrator(agent):
    from components.game_engine import GameEngine
    from orchestrator.pipeline_integration import PipelineOrchestrator

    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.game_engine = GameEngine()
    orchestrator.agents = {"combat": agent}
    orchestrator._schema_cache = None
    return orchestrator


def _run(orchestrator, agent, scenario=None):
    scenario = scenario or {"scene": "Voidbringers attack!",
                            "choices": [{"combat_trigger": True}]}
    dto = {"_game_engine_ref": orchestrator.game_engine, "force_combat": True}
    return orchestrator._maybe_run_combat(scenario, dto)


class TestTheTurnIsReportedAsSuccessful:
    def test_a_resolved_combat_reports_success(self):
        """
        Without this the game loop discards the whole turn — the exact bug: a
        clean `outcome=defeat, rounds=4` followed by
        `Processing failed: Unknown error`.
        """
        agent = _StubAgent()
        result = _run(_orchestrator(agent), agent)
        assert result is not None
        assert result.get("success") is True, (
            "the game loop gates on `success`; without it the turn is thrown away")

    def test_the_response_type_is_lifted(self):
        """`_handle_response` dispatches on a TOP-LEVEL response_type."""
        agent = _StubAgent()
        result = _run(_orchestrator(agent), agent)
        assert result.get("response_type") == "combat_complete"

    def test_the_outcome_is_lifted(self):
        agent = _StubAgent(outcome="victory", rounds=3)
        result = _run(_orchestrator(agent), agent)
        assert result["outcome"] == "victory"
        assert result["rounds"] == 3

    def test_the_narration_reaches_the_top_level(self):
        agent = _StubAgent(narrative="Aggi stands over the fallen scout.")
        result = _run(_orchestrator(agent), agent)
        assert "Aggi stands over" in result.get("formatted_response", "")

    def test_an_existing_success_flag_is_respected(self):
        """Never overwrite an agent that already reports failure."""
        class _Failing:
            def run(self, dto):
                return {"success": False, "error": "combat blew up"}

        agent = _Failing()
        result = _run(_orchestrator(agent), agent)
        assert result["success"] is False


class TestTheNestedEnvelopeIsUnwrapped:
    """
    `_handle_unknown` assigned `response_data["response"]` straight to
    `formatted_response`. For combat that is a DICT, so the player got the canned
    "The adventure continues" line after a real encounter.
    """

    def _handle(self, payload):
        from haystack_dnd_game import HaystackDnDGame

        game = HaystackDnDGame.__new__(HaystackDnDGame)
        return game._handle_unknown(payload)

    def test_a_dict_envelope_yields_its_narrative(self):
        result = self._handle({"response": {"narrative": "The scout falls."}})
        assert result["formatted_response"] == "The scout falls."

    def test_the_result_is_always_a_string(self):
        """A dict here becomes a dict in the player's terminal."""
        result = self._handle({"response": {"outcome": "defeat", "rounds": 4}})
        assert isinstance(result["formatted_response"], str)

    def test_an_outcome_without_narration_is_still_described(self):
        result = self._handle({"response": {"outcome": "victory", "rounds": 3}})
        text = result["formatted_response"]
        assert "victory" in text and "3" in text

    def test_a_string_envelope_still_works(self):
        """The legacy shape must not regress."""
        result = self._handle({"response": "Plain text reply"})
        assert result["formatted_response"] == "Plain text reply"

    def test_a_scene_payload_still_works(self):
        result = self._handle({"scene": "A quiet plateau.", "choices": []})
        assert "A quiet plateau." in result["formatted_response"]


class TestTheTurnIsRecorded:
    def test_a_successful_combat_turn_can_record_a_beat(self):
        """
        The beat is written by process_scenario_state_updates(), which the loop
        only reaches on the success path. A live run recorded ZERO beats for this
        reason while 2.2 itself was working.
        """
        from components.game_engine import GameEngine

        engine = GameEngine()
        engine.process_scenario_state_updates(
            {"scene": "The scouts overwhelm Aggi.", "choices": []}, 1)
        assert engine.get_narrative_beats(10), (
            "a resolved turn recorded no narrative beat")
