"""
Tests for AoE spell target expansion (area_of_effect node).

Verifies that spells with area_of_effect auto-expand to all entities within
range of the chosen target, with each making their own save/taking their own
damage, while single-target spells remain unchanged.
"""

import pytest
from components.combat.spell_compiler import compile_spell
from components.srd_rules import get_srd_rules
from config.logging_config import get_logger

logger = get_logger(__name__)


def test_fireball_compiles_with_aoe_node():
    """Fireball should compile with an area_of_effect node wrapping its save/damage."""
    logger.info("🧪 Testing Fireball compilation includes AoE node")

    srd = get_srd_rules()
    spell = srd.spell("Fireball")
    compiled = compile_spell(spell, slot_level=3)

    assert compiled is not None
    assert not compiled.needs_adjudication
    assert compiled.area_of_effect == {"type": "sphere", "size": 20}

    # The automation should be: target -> area_of_effect -> save -> damage
    assert len(compiled.automation) == 1
    target_node = compiled.automation[0]
    assert target_node["type"] == "target"
    assert target_node["target"] == "chosen"

    effects = target_node["effects"]
    assert len(effects) == 1
    aoe_node = effects[0]
    assert aoe_node["type"] == "area_of_effect"
    assert aoe_node["shape"] == "sphere"
    assert aoe_node["size"] == 20

    # Inside the AoE should be the save/damage tree
    aoe_effects = aoe_node["effects"]
    assert len(aoe_effects) == 1
    save_node = aoe_effects[0]
    assert save_node["type"] == "save"
    assert save_node["stat"] == "dexterity"

    logger.info("✅ Fireball compiles with proper AoE wrapping")


def test_single_target_spell_unchanged():
    """Magic Missile (no AoE) should compile without area_of_effect node."""
    logger.info("🧪 Testing single-target spell has no AoE node")

    srd = get_srd_rules()
    spell = srd.spell("Magic Missile")
    compiled = compile_spell(spell, slot_level=1)

    assert compiled is not None
    assert compiled.area_of_effect is None

    # Should be: target -> damage (no AoE wrapper)
    target_node = compiled.automation[0]
    assert target_node["type"] == "target"

    effects = target_node["effects"]
    # Magic Missile is force damage, no save, automatic hit
    # The first effect should NOT be area_of_effect
    assert all(e["type"] != "area_of_effect" for e in effects)

    logger.info("✅ Single-target spell unchanged (no AoE node)")


def test_burning_hands_has_aoe():
    """Burning Hands is a 1st-level AoE spell with a 15-foot cone."""
    logger.info("🧪 Testing Burning Hands (cone AoE)")

    srd = get_srd_rules()
    spell = srd.spell("Burning Hands")
    compiled = compile_spell(spell, slot_level=1)

    assert compiled is not None
    assert not compiled.needs_adjudication
    assert compiled.area_of_effect is not None
    assert compiled.area_of_effect["type"] == "cone"
    assert compiled.area_of_effect["size"] == 15

    # Check it has the AoE node
    target_node = compiled.automation[0]
    aoe_node = target_node["effects"][0]
    assert aoe_node["type"] == "area_of_effect"
    assert aoe_node["shape"] == "cone"
    assert aoe_node["size"] == 15

    logger.info("✅ Burning Hands compiles with cone AoE")


def test_cure_wounds_no_aoe():
    """Cure Wounds is a single-target healing spell."""
    logger.info("🧪 Testing Cure Wounds (no AoE)")

    srd = get_srd_rules()
    spell = srd.spell("Cure Wounds")
    compiled = compile_spell(spell, slot_level=1)

    assert compiled is not None
    assert compiled.area_of_effect is None

    # Should have no AoE node in the tree
    target_node = compiled.automation[0]
    effects = target_node["effects"]
    assert all(e["type"] != "area_of_effect" for e in effects)

    logger.info("✅ Cure Wounds has no AoE node")


def test_thunderwave_has_aoe():
    """Thunderwave is a 1st-level AoE spell with a 15-foot cube."""
    logger.info("🧪 Testing Thunderwave (cube AoE)")

    srd = get_srd_rules()
    spell = srd.spell("Thunderwave")
    compiled = compile_spell(spell, slot_level=1)

    assert compiled is not None
    assert not compiled.needs_adjudication
    assert compiled.area_of_effect is not None
    assert compiled.area_of_effect["type"] == "cube"
    assert compiled.area_of_effect["size"] == 15

    # Check it has the AoE node
    target_node = compiled.automation[0]
    aoe_node = target_node["effects"][0]
    assert aoe_node["type"] == "area_of_effect"
    assert aoe_node["shape"] == "cube"
    assert aoe_node["size"] == 15

    logger.info("✅ Thunderwave compiles with cube AoE")


def test_aoe_saves_are_inside_aoe_node():
    """
    For an AoE spell with a save, the save node should be INSIDE the AoE node.

    This ensures each target in the area makes their own save, rather than all
    targets sharing one save result.
    """
    logger.info("🧪 Testing save node is inside AoE node")

    srd = get_srd_rules()
    spell = srd.spell("Fireball")
    compiled = compile_spell(spell, slot_level=3)

    # Navigate: target -> area_of_effect -> save -> damage
    target_node = compiled.automation[0]
    aoe_node = target_node["effects"][0]
    assert aoe_node["type"] == "area_of_effect"

    # The save should be inside the AoE's effects
    aoe_effects = aoe_node["effects"]
    save_node = aoe_effects[0]
    assert save_node["type"] == "save"

    # The damage is in the fail branch
    fail_effects = save_node["fail"]
    assert len(fail_effects) > 0
    assert fail_effects[0]["type"] == "damage"

    # The success branch should have halved damage (save-for-half)
    success_effects = save_node["success"]
    assert len(success_effects) > 0
    assert success_effects[0]["type"] == "damage"
    assert success_effects[0]["multiplier"] == 0.5

    logger.info("✅ Save and damage nodes correctly nested in AoE")


def test_spell_attack_aoe_spell():
    """
    Some AoE spells might use spell attacks rather than saves.
    Verify the structure still works (though this is rarer).
    """
    logger.info("🧪 Testing spell attack inside AoE (if such a spell exists)")

    srd = get_srd_rules()
    # Most AoE spells use saves, not attacks. If we find one, test it.
    # For now, just verify Fireball's structure is correct.
    # This test is a placeholder for completeness.

    spell = srd.spell("Fireball")
    compiled = compile_spell(spell, slot_level=3)

    # Fireball uses a save, not an attack
    target_node = compiled.automation[0]
    aoe_node = target_node["effects"][0]
    save_node = aoe_node["effects"][0]
    assert save_node["type"] == "save"  # Not spell_attack

    logger.info("✅ AoE structure verified (Fireball uses save)")


def test_aoe_with_zero_size_falls_back_to_single_target():
    """
    If an AoE spell somehow has size=0, it should fall back to single-target
    behavior rather than wrapping in a broken AoE node.
    """
    logger.info("🧪 Testing AoE with size=0 falls back")

    srd = get_srd_rules()
    spell = srd.spell("Fireball")

    # Manually modify to have size 0
    spell_copy = dict(spell)
    spell_copy["area_of_effect"] = {"type": "sphere", "size": 0}

    compiled = compile_spell(spell_copy, slot_level=3)

    # Should fall back to regular target behavior (no AoE node)
    target_node = compiled.automation[0]
    effects = target_node["effects"]

    # The first effect should be the save, NOT an AoE node
    assert effects[0]["type"] != "area_of_effect"

    logger.info("✅ AoE with size=0 falls back to single-target")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
