"""
A finished campaign must stop accepting turns.

The ending was ANNOUNCED but never ENFORCED. Measured live: Aggi died in combat on
turn 2, and turns 3-6 were still processed. The DM narrated four variations of "the
eternal night of oblivion" — two of them byte-identical — no turn could change
anything, and the in-world clock never moved, because a corpse cannot travel or rest.

Every downstream guard was already correct, which is what made this hard to see:

    ⚠️ Skipping combat: no party member can act (dead, or stably unconscious)
    💀 Total party defeat — campaign marked ended (party_defeated)

and the DM itself wrote *"No further actions can be taken in this campaign."*
Nothing acted on any of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]


def _game(ending=None, rounds=None):
    from components.game_engine import GameEngine
    from haystack_dnd_game import HaystackDnDGame

    game = HaystackDnDGame.__new__(HaystackDnDGame)
    game.game_engine = GameEngine()
    narrative = game.game_engine.game_state.narrative_context
    if ending:
        narrative["campaign_ended"] = True
        narrative["campaign_ending"] = ending
        if rounds is not None:
            narrative["campaign_ending_rounds"] = rounds
    return game


class TestTheGateOpensAndCloses:
    def test_a_live_campaign_is_not_gated(self):
        """Both directions — the gate must not block ordinary play."""
        assert _game()._campaign_ending_notice() is None

    def test_a_defeated_party_is_gated(self):
        notice = _game("party_defeated", rounds=9)._campaign_ending_notice()
        assert notice is not None
        assert "over" in notice.lower()

    def test_a_completed_campaign_is_gated(self):
        notice = _game("objectives_met")._campaign_ending_notice()
        assert notice is not None
        assert "complete" in notice.lower()

    def test_defeat_and_victory_read_differently(self):
        """The player must be told WHICH ending they reached."""
        defeat = _game("party_defeated")._campaign_ending_notice()
        victory = _game("objectives_met")._campaign_ending_notice()
        assert defeat != victory
        assert "fallen" in defeat.lower()

    def test_the_round_count_is_reported_when_known(self):
        assert "9 rounds" in _game("party_defeated", rounds=9)._campaign_ending_notice()

    def test_a_missing_round_count_does_not_break_it(self):
        assert _game("party_defeated")._campaign_ending_notice() is not None

    def test_the_player_is_offered_a_way_out(self):
        """A finished campaign should not be a dead end with no route back."""
        for ending in ("party_defeated", "objectives_met"):
            assert "load" in _game(ending)._campaign_ending_notice().lower()

    def test_a_broken_engine_does_not_gate(self):
        """Failing open is right here: never block play because a lookup failed."""
        from haystack_dnd_game import HaystackDnDGame

        game = HaystackDnDGame.__new__(HaystackDnDGame)
        game.game_engine = None
        assert game._campaign_ending_notice() is None


class TestTheTurnIsActuallyRefused:
    """
    Assert the GATE IS CALLED, not just that the helper works. The four subsystems
    that shipped unreachable all had working helpers.
    """

    def test_resolve_turn_consults_the_gate(self):
        import inspect

        from haystack_dnd_game import HaystackDnDGame

        source = inspect.getsource(HaystackDnDGame.resolve_turn)
        assert "_campaign_ending_notice" in source, (
            "resolve_turn does not check whether the campaign has ended, so play "
            "continues past the ending")

    def test_the_gate_precedes_any_llm_work(self):
        """
        A refused turn must cost nothing. Gating after the orchestrator call would
        still bill tokens for a turn that cannot change anything.
        """
        import inspect

        from haystack_dnd_game import HaystackDnDGame

        source = inspect.getsource(HaystackDnDGame.resolve_turn)
        gate = source.index("_campaign_ending_notice")
        work = source.index("process_request")
        assert gate < work, "the endgame gate runs after the pipeline call"

    def test_the_refusal_is_not_recorded_as_a_player_turn(self):
        """
        Recording refused turns would pad the history and let a dead campaign keep
        growing its transcript.
        """
        import inspect

        from haystack_dnd_game import HaystackDnDGame

        source = inspect.getsource(HaystackDnDGame.resolve_turn)
        gate = source.index("_campaign_ending_notice")
        remember = source.index('self._remember("user"')
        assert gate < remember, (
            "the player's input is recorded before the endgame gate refuses it")
