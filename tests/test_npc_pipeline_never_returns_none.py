"""
A pipeline must never hand `None` back to the game loop.

`play_turn()` treats a `None` response as a total pipeline failure and tells the
player *"The magical forces seem disrupted"*, discarding the whole turn. The NPC
path did exactly that: `agent_result["npc_response"]` can be present with a **None
value** when the NPC agent ends on a tool call rather than text, and
`return npc_response` passed that straight up.

Two symptoms, one cause. The same None also broke memory storage one line earlier —
`_remember_npc_interaction` calls `.get` on it:

    ⚠️ Could not store NPC memory for someone to talk to:
       'NoneType' object has no attribute 'get'
    ❌ Orchestrator returned None - pipeline failure

Found by the playtest turn "I look for someone to talk to, and ask them about the
Voidbringers" — a turn that only existed because the inputs had been six variants of
"I look around", so the NPC pipeline had never been exercised through gameplay.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]


def _orchestrator(pipeline_result):
    """An orchestrator whose NPC pipeline returns exactly `pipeline_result`."""
    from orchestrator.pipeline_integration import PipelineOrchestrator

    class _Pipeline:
        def run(self, inputs):
            return pipeline_result

    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.pipelines = {"npc_interaction": _Pipeline()}
    orchestrator.game_engine = None
    orchestrator.character_manager = None
    return orchestrator


def _dto():
    return {"type": "npc_interaction", "player_input": "ask about Voidbringers",
            "target": "guard", "correlation_id": "test-1"}


class TestTheNpcPathNeverReturnsNone:
    def test_a_none_npc_response_becomes_an_error_dict(self):
        """The exact live shape: the key present, the value None."""
        orchestrator = _orchestrator({"npc_controller": {"npc_response": None}})
        result = orchestrator._run_npc_pipeline(_dto())

        assert result is not None, (
            "returning None makes the game loop discard the whole turn")
        assert isinstance(result, dict)
        assert "error" in result

    def test_a_non_dict_response_is_rejected(self):
        """A bare string would break every consumer that calls .get on it."""
        orchestrator = _orchestrator({"npc_controller": {"npc_response": "hello"}})
        result = orchestrator._run_npc_pipeline(_dto())
        assert isinstance(result, dict) and "error" in result

    def test_a_real_response_passes_through(self):
        """Both directions — the guard must not break the working path.

        The dialogue is now returned INSIDE a turn envelope rather than bare.
        `haystack_dnd_game.play_turn` gates on `response_dict["success"]` and
        `_handle_response` dispatches on `response_type`, reading the dialogue from
        `npc_response["dialogue"]` (`haystack_dnd_game.py:1001-1018`). Returning the
        bare dict — which is what this test used to assert — meant every NPC
        conversation reached the player as "The world seems momentarily confused by
        your action", logged as `Processing failed: Unknown error`, even though the NPC
        had answered in character. Verified against the live LLM before and after.
        """
        payload = {"dialogue": "The Voidbringers came at dawn.",
                   "npc_name": "Guard"}
        orchestrator = _orchestrator({"npc_controller": {"npc_response": payload}})
        result = orchestrator._run_npc_pipeline(_dto())

        # The envelope the game loop requires...
        assert result["success"] is True, "the turn loop gates on `success`"
        assert result["response_type"] == "npc_interaction"
        # ...with the dialogue still intact where `_handle_npc` looks for it.
        assert result["npc_response"]["dialogue"] == "The Voidbringers came at dawn."
        assert "The Voidbringers came at dawn." in result["formatted_response"]

    def test_a_missing_key_is_still_an_error_dict(self):
        orchestrator = _orchestrator({"npc_controller": {}})
        result = orchestrator._run_npc_pipeline(_dto())
        assert isinstance(result, dict) and "error" in result

    def test_a_missing_controller_is_still_an_error_dict(self):
        orchestrator = _orchestrator({})
        result = orchestrator._run_npc_pipeline(_dto())
        assert isinstance(result, dict) and "error" in result

    def test_memory_storage_is_skipped_for_a_none_response(self):
        """
        Otherwise `_remember_npc_interaction` raises on `.get` — which is how this
        surfaced as two separate warnings from one cause.
        """
        recorded = []
        orchestrator = _orchestrator({"npc_controller": {"npc_response": None}})
        orchestrator._remember_npc_interaction = (
            lambda *a, **k: recorded.append(a))

        orchestrator._run_npc_pipeline(_dto())
        assert not recorded, "tried to store a None exchange"


class TestProcessRequestNeverReturnsNone:
    """
    The backstop. Whatever a pipeline does, the game loop must receive a dict — a
    turn that partly succeeded should not be thrown away wholesale.
    """

    def test_a_none_pipeline_result_becomes_an_error_response(self, monkeypatch):
        from orchestrator.pipeline_integration import PipelineOrchestrator

        orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
        monkeypatch.setattr(orchestrator, "_process_dto_pipeline",
                            lambda dto: None, raising=False)

        result = orchestrator.process_request(
            {"type": "gameplay_turn", "correlation_id": "c1",
             "player_input": "look"})
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("response_type") == "error"
