"""
Unit tests for InvestiturePointLedger (plan 2.9).

WHAT THIS TESTS
--------------
The ledger that spends `CharacterData.investiture_points` against the
book-accurate cost table in `CosmereRules.investiture_cost()`. Before this,
`investiture_cost()` existed with zero callers.

ASSERTIONS ON OUTCOMES
----------------------
Tests assert on observable state changes: IP counts actually fell, cantrips
stay free, refills reach maximum. Pattern-matched from test_spellcasting.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.investiture_ledger import (MAX_ART_LEVEL,
                                                  InvestiturePointLedger,
                                                  InvestitureSpend)
from components.cosmere_rules import CosmereRules


@pytest.fixture
def setup():
    """A Truthwatcher with 10/12 IP and a depleted Elsecaller with 0/8 IP."""
    manager = CharacterManager()

    # Truthwatcher with investiture points
    manager.add_character({
        "character_id": "Renarin",
        "name": "Renarin",
        "level": 5,
        "character_class": "Truthwatcher",
        "race": "Human",
        "background": "Noble",
        "ability_scores": {
            "strength": 10, "dexterity": 12, "constitution": 14,
            "intelligence": 16, "wisdom": 18, "charisma": 13
        },
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 14,
        "proficiency_bonus": 3,
        "investiture_points": {"current": 10, "maximum": 12}
    })

    # Elsecaller (special 1-IP rule), depleted
    manager.add_character({
        "character_id": "Jasnah",
        "name": "Jasnah",
        "level": 7,
        "character_class": "Elsecaller",
        "race": "Human",
        "background": "Scholar",
        "ability_scores": {
            "strength": 8, "dexterity": 12, "constitution": 13,
            "intelligence": 20, "wisdom": 16, "charisma": 14
        },
        "hit_points": {"current": 50, "maximum": 50, "temporary": 0},
        "armor_class": 13,
        "proficiency_bonus": 3,
        "investiture_points": {"current": 0, "maximum": 8}
    })

    # Character with no investiture points at all
    manager.add_character({
        "character_id": "Grunt",
        "name": "Grunt",
        "level": 3,
        "character_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "ability_scores": {
            "strength": 16, "dexterity": 14, "constitution": 15,
            "intelligence": 10, "wisdom": 12, "charisma": 8
        },
        "hit_points": {"current": 30, "maximum": 30, "temporary": 0},
        "armor_class": 16,
        "proficiency_bonus": 2,
    })

    rules = CosmereRules()
    ledger = InvestiturePointLedger(manager, rules)

    return ledger, manager


# ---------------------------------------------------------------------------
# 1. Reading the pool
# ---------------------------------------------------------------------------

class TestPoolReading:
    """IP current/maximum getters."""

    def test_current_returns_available_ip(self, setup):
        ledger, _ = setup
        assert ledger.current("Renarin") == 10

    def test_maximum_returns_capacity(self, setup):
        ledger, _ = setup
        assert ledger.maximum("Renarin") == 12

    def test_has_any_true_when_ip_remains(self, setup):
        ledger, _ = setup
        assert ledger.has_any("Renarin") is True

    def test_has_any_false_when_depleted(self, setup):
        ledger, _ = setup
        assert ledger.has_any("Jasnah") is False

    def test_can_afford_checks_cost(self, setup):
        ledger, _ = setup
        assert ledger.can_afford("Renarin", 5) is True
        assert ledger.can_afford("Renarin", 15) is False

    def test_unknown_character_returns_zero(self, setup):
        ledger, _ = setup
        assert ledger.current("Nobody") == 0
        assert ledger.maximum("Nobody") == 0


# ---------------------------------------------------------------------------
# 2. Spending IP
# ---------------------------------------------------------------------------

class TestInvestitureSpending:
    """Assert the count MOVES when an art is cast."""

    def test_cantrips_cost_nothing_and_always_succeed(self, setup):
        ledger, _ = setup
        result = ledger.spend("Renarin", art_level=0)
        assert result.spent is True
        assert result.cost == 0
        assert "cantrip" in result.reason.lower()
        assert ledger.current("Renarin") == 10, "cantrip must not spend IP"

    def test_first_level_art_costs_2_ip(self, setup):
        """Book rule: 1st-level art = 2 IP."""
        ledger, manager = setup
        before = ledger.current("Renarin")
        result = ledger.spend("Renarin", art_level=1)
        after = ledger.current("Renarin")

        assert result.spent is True
        assert result.cost == 2
        assert after == before - 2

    def test_second_level_art_costs_3_ip(self, setup):
        """Book rule: 2nd-level art = 3 IP."""
        ledger, _ = setup
        before = ledger.current("Renarin")
        result = ledger.spend("Renarin", art_level=2)
        after = ledger.current("Renarin")

        assert result.spent is True
        assert result.cost == 3
        assert after == before - 3

    def test_fifth_level_art_costs_7_ip(self, setup):
        """Book rule: 5th-level art = 7 IP."""
        ledger, _ = setup
        before = ledger.current("Renarin")
        result = ledger.spend("Renarin", art_level=5)
        after = ledger.current("Renarin")

        assert result.spent is True
        assert result.cost == 7
        assert after == before - 7

    def test_refuses_when_insufficient_ip(self, setup):
        ledger, _ = setup
        # Renarin has 10 IP; a 5th-level art costs 7, leaving 3
        ledger.spend("Renarin", art_level=5)
        # Try another 5th-level art (needs 7, has 3)
        result = ledger.spend("Renarin", art_level=5)

        assert result.spent is False
        assert "insufficient" in result.reason.lower()
        assert result.cost == 7

    def test_refuses_when_depleted(self, setup):
        ledger, _ = setup
        result = ledger.spend("Jasnah", art_level=1)

        assert result.spent is False
        assert "insufficient" in result.reason.lower()

    def test_refuses_when_no_ip_pool_at_all(self, setup):
        ledger, _ = setup
        result = ledger.spend("Grunt", art_level=1)

        assert result.spent is False
        assert "no investiture points" in result.reason.lower()

    def test_elsecaller_always_spends_exactly_1_ip(self, setup):
        """
        Elsecaller exception: any leveled art costs 1 IP (HB rule).

        Re-supply Jasnah with 5 IP so she can cast.
        """
        ledger, manager = setup
        manager.characters["Jasnah"].investiture_points["current"] = 5

        result = ledger.spend("Jasnah", art_level=5, order="Elsecaller")

        assert result.spent is True
        assert result.cost == 1, "Elsecaller leveled arts cost 1 IP, not 7"
        assert ledger.current("Jasnah") == 4

    def test_invalid_art_level_refuses(self, setup):
        ledger, _ = setup
        result = ledger.spend("Renarin", art_level=-1)
        assert result.spent is False

    def test_art_level_above_max_refuses(self, setup):
        ledger, _ = setup
        result = ledger.spend("Renarin", art_level=10)
        assert result.spent is False
        assert "no defined cost" in result.reason.lower() or "no level 10 art" in result.reason.lower()


# ---------------------------------------------------------------------------
# 3. Restore (refund when cast fails)
# ---------------------------------------------------------------------------

class TestRestore:
    """Give IP back when a cast is refused after payment."""

    def test_restore_adds_ip_back(self, setup):
        ledger, _ = setup
        ledger.spend("Renarin", art_level=2)  # costs 3
        before = ledger.current("Renarin")
        refunded = ledger.restore("Renarin", 3)

        assert refunded == before + 3
        assert ledger.current("Renarin") == before + 3

    def test_restore_clamps_to_maximum(self, setup):
        ledger, _ = setup
        maximum = ledger.maximum("Renarin")
        refunded = ledger.restore("Renarin", 999)

        assert refunded == maximum
        assert ledger.current("Renarin") == maximum


# ---------------------------------------------------------------------------
# 4. Long rest refresh
# ---------------------------------------------------------------------------

class TestLongRestRefresh:
    """Full IP restore on long rest (book rule)."""

    def test_refresh_restores_to_maximum(self, setup):
        ledger, _ = setup
        ledger.spend("Renarin", art_level=5)  # spends 7, leaving 3
        assert ledger.current("Renarin") == 3

        success = ledger.refresh_on_long_rest("Renarin")

        assert success is True
        assert ledger.current("Renarin") == ledger.maximum("Renarin")

    def test_refresh_restores_depleted_character(self, setup):
        ledger, _ = setup
        assert ledger.current("Jasnah") == 0

        ledger.refresh_on_long_rest("Jasnah")

        assert ledger.current("Jasnah") == ledger.maximum("Jasnah")

    def test_refresh_fails_when_no_pool(self, setup):
        ledger, _ = setup
        success = ledger.refresh_on_long_rest("Grunt")

        assert success is False

    def test_refresh_fails_for_unknown_character(self, setup):
        ledger, _ = setup
        success = ledger.refresh_on_long_rest("Nobody")

        assert success is False


# ---------------------------------------------------------------------------
# 5. Integration: the cost table is actually consulted
# ---------------------------------------------------------------------------

class TestCostTable:
    """
    `investiture_cost()` existed with zero callers. Verify it is now reachable.
    """

    def test_cost_table_is_consulted(self, setup):
        """Art levels 1-5 have different costs; assert they all differ."""
        ledger, _ = setup
        costs = []
        for level in range(1, MAX_ART_LEVEL + 1):
            result = ledger.spend("Renarin", art_level=level)
            if result.spent:
                costs.append(result.cost)
                ledger.restore("Renarin", result.cost)  # refund for next test

        # Book costs: 1st=2, 2nd=3, 3rd=5, 4th=6, 5th=7
        assert costs == [2, 3, 5, 6, 7], "cost table must match the book"
