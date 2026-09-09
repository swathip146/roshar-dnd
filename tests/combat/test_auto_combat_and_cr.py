"""
Unattended combat + CR balancing — both raised by a live playtest.

1. Combat ran INTERACTIVELY during the test: it printed "Choose action type
   (1-2):" and waited on a human. The naive stub (always answer "1") is not a
   fix — menu item 1 is whatever the registry ordered first, which in the live
   run was *Lashing* against a shadow creature immune to it, so the fight could
   not progress. AutoCombatPlayer chooses by what the action DOES.

2. Enemy levels did not match the party. estimated_cr comes from the
   scene-extraction LLM, which read "Voidbringers" and returned CR 3 x3 for a
   LEVEL 1 party — three 65 HP / AC 16 soldiers against one character with 8 max
   HP. party_level was passed to the stat generator as advisory context only and
   nothing enforced it, so the encounter was unwinnable by construction.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from components.combat.auto_combat_player import AutoCombatPlayer
from components.combat.combat_initializer import CombatInitializer


pytestmark = [pytest.mark.combat, pytest.mark.unit]


# Verbatim from the live combat menu.
LIVE_MENU = [
    "  1. Attack with weapon → Shadow-Fused Soldier (HP: 65/65)",
    "  2. Attack with weapon → Shadow-Fused Soldier (HP: 65/65)",
    "  3. Attack with weapon → Shadow-Fused Soldier (HP: 65/65)",
    "  4. Manipulate gravity (Windrunner/Skybreaker) → Shadow-Fused Soldier (HP: 65/65)",
    "  7. Heal wounds with Progression (Edgedancer/Truthwatcher) → Aggi (HP: 13/32)",
]


def _feed(player: AutoCombatPlayer, lines) -> None:
    for line in lines:
        player.observe_options(line)


class TestAutoPlayerChoosesByMeaning:

    def test_attacks_when_healthy(self):
        player = AutoCombatPlayer(hp_fraction=lambda: 1.0)
        _feed(player, LIVE_MENU)
        assert player("Aggi> Choose action (1-9): ") == "1"

    def test_heals_when_badly_hurt(self):
        """13/32 HP is 0.41; below the 0.35 threshold it should heal."""
        player = AutoCombatPlayer(hp_fraction=lambda: 0.2)
        _feed(player, LIVE_MENU)
        # The heal option is at index 5 in the recorded list (1-based).
        choice = int(player("Aggi> Choose action (1-9): "))
        assert "Heal" in player._options[choice - 1]

    def test_does_not_heal_when_healthy(self):
        player = AutoCombatPlayer(hp_fraction=lambda: 0.9)
        _feed(player, LIVE_MENU)
        choice = int(player("Aggi> Choose action (1-9): "))
        assert "Attack" in player._options[choice - 1]

    def test_never_exceeds_the_prompt_limit(self):
        """Answering out of range would loop the prompt 10 times."""
        player = AutoCombatPlayer()
        _feed(player, LIVE_MENU)
        for limit in (1, 2, 3, 9):
            choice = int(player(f"Choose action (1-{limit}): "))
            assert 1 <= choice <= limit

    def test_always_returns_a_digit_string(self):
        """_prompt_choice rejects anything non-numeric."""
        player = AutoCombatPlayer()
        _feed(player, LIVE_MENU)
        for prompt in ("Choose action type (1-2): ", "Choose action (1-9): "):
            assert player(prompt).isdigit()

    def test_works_with_no_options_observed(self):
        """Must not crash if the menu was not captured."""
        player = AutoCombatPlayer()
        assert player("Choose action (1-3): ").isdigit()

    def test_records_its_decisions(self):
        player = AutoCombatPlayer()
        _feed(player, LIVE_MENU)
        player("Choose action (1-9): ")
        assert len(player.decisions) == 1

    def test_a_new_list_resets_the_options(self):
        """Option 1 starting a new block must not append to the old one."""
        player = AutoCombatPlayer()
        _feed(player, LIVE_MENU)
        _feed(player, ["  1. Dodge", "  2. Disengage"])
        assert len(player._options) == 2


class TestStdoutTapIsTransparent:

    def test_output_still_reaches_stdout(self, capsys):
        player = AutoCombatPlayer()
        tap = player.install()
        try:
            print("  1. Attack with weapon → Foe")
        finally:
            tap.uninstall()
        assert "Attack with weapon" in capsys.readouterr().out

    def test_options_are_captured_from_print(self):
        player = AutoCombatPlayer()
        tap = player.install()
        try:
            print("  1. Attack with weapon → Foe")
            print("  2. Heal wounds with Progression → Aggi")
        finally:
            tap.uninstall()
        assert len(player._options) == 2


class TestCRIsClampedToTheParty:

    def _initializer(self, difficulty="medium"):
        stub = CombatInitializer.__new__(CombatInitializer)
        stub.game_engine = type("E", (), {"difficulty": difficulty})()
        return stub

    def test_the_live_failure_is_prevented(self):
        """CR 3 x3 against a level 1 party was unwinnable by construction."""
        clamped = self._initializer()._balanced_cr(3, party_level=1, count=3)
        assert clamped < 1, f"CR {clamped} is still lethal for a level 1 party"

    def test_a_single_enemy_matches_party_level(self):
        assert self._initializer()._balanced_cr(3, party_level=1, count=1) == 1.0
        assert self._initializer()._balanced_cr(9, party_level=5, count=1) == 5.0

    def test_more_enemies_means_weaker_each(self):
        initializer = self._initializer()
        one = initializer._balanced_cr(9, party_level=6, count=1)
        three = initializer._balanced_cr(9, party_level=6, count=3)
        assert three < one

    def test_weak_requests_are_not_raised(self):
        """The story may call for something trivial; that must stand."""
        assert self._initializer()._balanced_cr(0.25, party_level=10, count=1) == 0.25

    def test_high_level_parties_get_real_enemies(self):
        assert self._initializer()._balanced_cr(3, party_level=10, count=2) == 3.0

    def test_difficulty_scales_the_budget(self):
        easy = self._initializer("easy")._balanced_cr(9, 4, 1)
        medium = self._initializer("medium")._balanced_cr(9, 4, 1)
        hard = self._initializer("hard")._balanced_cr(9, 4, 1)
        assert easy < medium < hard

    def test_never_returns_zero(self):
        """A CR 0 enemy has no stats to fight."""
        assert self._initializer("easy")._balanced_cr(3, party_level=1, count=8) > 0

    def test_junk_input_does_not_raise(self):
        initializer = self._initializer()
        assert initializer._balanced_cr(None, 1, 1) > 0
        assert initializer._balanced_cr("abc", 1, 1) > 0
        assert initializer._balanced_cr(3, None, None) > 0

    def test_unknown_difficulty_defaults_to_medium(self):
        odd = self._initializer("bewildering")._balanced_cr(9, 4, 1)
        medium = self._initializer("medium")._balanced_cr(9, 4, 1)
        assert odd == medium
