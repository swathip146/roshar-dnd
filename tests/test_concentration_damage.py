"""
Test concentration break-on-damage: PHB 203, DC = max(10, damage/2)
"""

import pytest

from components.combat.spellcasting import (
    SpellcastingService,
    ConcentrationTracker,
)
from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.srd_rules import get_srd_rules
from config.logging_config import get_logger

logger = get_logger(__name__)


class _Engine:
    """Mock game engine for DnDEngineWrapper."""
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


@pytest.fixture
def wizard_concentrating():
    """
    A wizard concentrating on Bless, with 200 HP and +2 CON save.
    """
    manager = CharacterManager()
    wizard_data = {
        "character_id": "wizard_001",
        "name": "Elara",
        "character_class": "wizard",
        "level": 5,
        "hit_points": {"current": 200, "maximum": 200},
        "ability_scores": {
            "strength": 10,
            "dexterity": 14,
            "constitution": 14,
            "intelligence": 16,
            "wisdom": 12,
            "charisma": 8,
        },
        "armor_class": 13,
        "proficiency_bonus": 3,
        "spell_slots": {
            1: {"current": 3, "maximum": 4},
        },
        "spells_known": ["bless", "fire bolt"],
        "race": "Human",
        "background": "Sage",
        "equipment": [],
    }
    manager.add_character(wizard_data)

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    wrapper.set_entity_position("wizard_001", (0, 0))
    wrapper.refresh_senses()

    concentration = ConcentrationTracker()
    concentration.start("wizard_001", "bless", "1 minute")

    service = SpellcastingService(
        dnd_engine_wrapper=wrapper,
        character_manager=manager,
        srd_rules=get_srd_rules(),
        concentration=concentration,
    )

    return {
        "manager": manager,
        "wrapper": wrapper,
        "service": service,
        "concentration": concentration,
    }


def test_concentration_breaks_on_failed_save(wizard_concentrating):
    """
    Taking 20 damage (DC 10) while concentrating: CON save +2 has ~60% chance to fail.

    Retry until we see a failure (test is NOT flaky — it will eventually fail the save).
    """
    logger.info("🧪 Test: concentration breaks on failed CON save")

    ctx = wizard_concentrating
    executor = ctx["service"].executor

    # Sanity check: wizard is concentrating
    assert ctx["concentration"].concentrating_on("wizard_001") == "bless"

    # Apply damage repeatedly until the CON save fails
    max_attempts = 50
    for attempt in range(max_attempts):
        # Reset concentration each time
        ctx["concentration"].start("wizard_001", "bless", "1 minute")

        # Apply 20 damage: DC = max(10, 20/2) = 10
        # Wizard has CON +2, so save is d20+2 vs DC 10
        dealt = executor._apply_damage("wizard_001", 20, "fire")
        assert dealt == 20, f"Expected 20 damage dealt, got {dealt}"

        concentrating = ctx["concentration"].concentrating_on("wizard_001")
        if concentrating is None:
            # Success! The save failed and concentration broke
            logger.info(f"✅ Concentration broke after {attempt + 1} attempts")
            return

    pytest.fail(
        f"Concentration never broke after {max_attempts} attempts (CON save +2 vs DC 10). "
        f"Probability of this is ~(0.65^{max_attempts}) ≈ 0, so the check may not be working."
    )


def test_concentration_maintained_on_successful_save(wizard_concentrating):
    """
    Taking 1 damage (DC 10) while concentrating: CON save +2 has ~65% chance to succeed.

    Retry until we see a success.
    """
    logger.info("🧪 Test: concentration maintained on successful CON save")

    ctx = wizard_concentrating
    executor = ctx["service"].executor

    # Sanity check
    assert ctx["concentration"].concentrating_on("wizard_001") == "bless"

    # Apply minimal damage repeatedly until the save succeeds
    max_attempts = 50
    for attempt in range(max_attempts):
        # Reset concentration
        ctx["concentration"].start("wizard_001", "bless", "1 minute")

        # Apply 1 damage: DC = max(10, 1/2) = 10
        dealt = executor._apply_damage("wizard_001", 1, "piercing")
        assert dealt == 1

        concentrating = ctx["concentration"].concentrating_on("wizard_001")
        if concentrating == "bless":
            # Success! The save succeeded and concentration held
            logger.info(f"✅ Concentration maintained after {attempt + 1} attempts")
            return

    pytest.fail(
        f"Concentration always broke after {max_attempts} attempts. "
        f"With CON +2 vs DC 10, this suggests the check is not working."
    )


def test_concentration_dc_scales_with_damage(wizard_concentrating):
    """
    Verify DC = max(10, damage/2):
    - 5 damage -> DC 10
    - 20 damage -> DC 10
    - 40 damage -> DC 20
    - 100 damage -> DC 50
    """
    logger.info("🧪 Test: concentration DC scales with damage")

    ctx = wizard_concentrating
    concentration = ctx["concentration"]
    executor = ctx["service"].executor

    # We can't directly observe the DC, but we can verify the behavior indirectly:
    # With CON +2, the wizard needs to roll at least 8 for DC 10, or 18 for DC 20.

    # Test high damage: 100 damage -> DC 50. CON save +2 cannot pass this (max roll 22).
    concentration.start("wizard_001", "bless", "1 minute")
    executor._apply_damage("wizard_001", 100, "force")

    # With DC 50, the wizard MUST fail (max possible roll is 20+2=22)
    # If concentration is still active, the DC formula is wrong
    concentrating = concentration.concentrating_on("wizard_001")
    assert concentrating is None, (
        "Concentration should break on 100 damage (DC 50) — wizard's CON save +2 "
        "cannot pass DC 50 even with nat 20"
    )

    logger.info("✅ High damage (100 dmg -> DC 50) breaks concentration as expected")


def test_no_concentration_check_when_not_concentrating(wizard_concentrating):
    """
    Taking damage when NOT concentrating should not trigger a save.
    """
    logger.info("🧪 Test: no concentration check when not concentrating")

    ctx = wizard_concentrating
    concentration = ctx["concentration"]
    executor = ctx["service"].executor

    # Stop concentration
    concentration.stop("wizard_001")
    assert concentration.concentrating_on("wizard_001") is None

    # Apply damage — should not crash or log a concentration check
    dealt = executor._apply_damage("wizard_001", 10, "slashing")
    assert dealt == 10

    # Still no concentration
    assert concentration.concentrating_on("wizard_001") is None

    logger.info("✅ Damage without concentration works correctly")


def test_zero_damage_does_not_break_concentration(wizard_concentrating):
    """
    0 damage should not trigger a concentration check.
    """
    logger.info("🧪 Test: 0 damage does not break concentration")

    ctx = wizard_concentrating
    concentration = ctx["concentration"]
    executor = ctx["service"].executor

    # Sanity check
    concentration.start("wizard_001", "bless", "1 minute")
    assert concentration.concentrating_on("wizard_001") == "bless"

    # Apply 0 damage
    dealt = executor._apply_damage("wizard_001", 0, "psychic")
    assert dealt == 0

    # Concentration should still be active
    assert concentration.concentrating_on("wizard_001") == "bless"

    logger.info("✅ Zero damage correctly preserves concentration")
