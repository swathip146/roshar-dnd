"""
Combat turns must reach the player — regression guard.

`_handle_response` had NO branch for combat, so every resolved encounter fell through
to `_handle_unknown`, which looks for a TOP-LEVEL "scene" or "response" key. The combat
envelope has neither: `_run_combat_pipeline` builds `response_type="combat_complete"`
with the narrative nested in `scenario.scene`.

Measured against the live LLM: an 8-round encounter resolved cleanly ("✅ Combat
complete: defeat in 8 rounds", GameEngine updated, NPCs cleaned up) and the player was
shown "The adventure continues in unexpected ways...", logged as "Unrecognized response
format with keys: [...]". The fight happened; only its description was discarded — the
same shape as two other bugs this codebase has already fixed twice.

These tests need no LLM: the defect is in how the turn's envelope is DISPATCHED.
"""

from __future__ import annotations

import pytest

from haystack_dnd_game import HaystackDnDGame

pytestmark = pytest.mark.integration


def _game() -> HaystackDnDGame:
    """A HaystackDnDGame shell — `_handle_response` needs no live components."""
    game = HaystackDnDGame.__new__(HaystackDnDGame)
    game.current_scenario = {}
    game.current_choices = []
    return game


def _combat_envelope(response_type: str = "combat_complete",
                     scene: str = "🎉 VICTORY! You defeated your enemies in 9 rounds.",
                     ) -> dict:
    """The shape `_run_combat_pipeline` actually returns."""
    return {
        "success": True,
        "response_type": response_type,
        "scenario": {"scene": scene, "choices": [],
                     "gm_notes": "Combat: victory in 9 rounds"},
        "rag_result": None,
        "npc_response": None,
        "error": None,
    }


class TestCombatOutcomeReachesThePlayer:

    def test_a_resolved_encounter_is_narrated(self):
        result = _game()._handle_response(_combat_envelope())

        assert "VICTORY" in result["formatted_response"], (
            f"the combat narrative did not reach the player: "
            f"{result['formatted_response']!r}")
        assert "unexpected ways" not in result["formatted_response"], (
            "combat fell through to _handle_unknown's canned line")

    @pytest.mark.parametrize("response_type", [
        "combat_complete", "combat", "combat_start", "combat_ongoing",
    ])
    def test_every_combat_response_type_is_dispatched(self, response_type):
        """All four are produced by different points in the combat lifecycle."""
        scene = f"The fight continues ({response_type})."
        result = _game()._handle_response(_combat_envelope(response_type, scene))

        assert scene in result["formatted_response"], (
            f"{response_type!r} was not dispatched to a real formatter")

    def test_a_defeat_is_reported_too(self):
        """A party wipe must be narrated, not swallowed — it ends the campaign."""
        envelope = _combat_envelope(
            scene="💀 DEFEAT. The party falls after 8 rounds.")
        result = _game()._handle_response(envelope)

        assert "DEFEAT" in result["formatted_response"]

    def test_a_genuinely_unknown_shape_still_falls_back(self):
        """The fix must not swallow the unknown-format warning path."""
        result = _game()._handle_response({"response_type": "something_new"})

        assert result["formatted_response"], "an unknown shape produced no text"
        assert "unexpected ways" in result["formatted_response"], (
            "the honest fallback for a truly unrecognised envelope was removed")
