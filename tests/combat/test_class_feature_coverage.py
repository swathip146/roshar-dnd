"""
Coverage tests for the WIDENED class-feature table (all 12 base classes).

`data/rules/class_features/class_features.json` grew from 7 features / 6 classes to
every base class having at least one authored feature, and the engine
(`components/combat/class_features.py`) gained five generic, data-driven effect
nodes so far more of the 5e table can be expressed:

    ability_score_bonus   raise one ability SCORE      (Barbarian Primal Champion)
    ac_bonus              flat Armor Class bonus       (Fighter Defense style)
    temp_hp               Temporary Hit Points         (Ranger Tireless)
    speed_bonus           +Speed in feet               (Barbarian Fast Movement, Monk)
    advantage             Advantage on a save/attack   (Danger Sense, Steady Aim, ...)

This suite asserts on OBSERVABLE engine state, never on status strings, exactly as
`test_class_features.py` does:

  * every one of the 12 base classes now has >= 1 authored feature;
  * each new effect node executes and produces measured state (a raised ability
    score, +1 AC, temp HP in the pool, +10 movement, ADVANTAGE on the named value);
  * passives apply through `ClassFeatureEngine.apply_passives()` and are stripped by
    `clear_all()` — a Fighter's Defense +1 does not follow them into the next fight;
  * a representative ACTIVATED feature per martial class (Paladin Lay On Hands,
    Rogue Steady Aim, Ranger Tireless, Sorcerer Innate Sorcery, Barbarian Reckless
    Attack) fires in a real turn through the CombatActionResolver;
  * the `_meta.needs_subsystem` list is populated (Wild Shape, Ki, Metamagic, ...).

The engine rolls through its OWN DiceRoller, so where a die value must be pinned a
fixed-die stub is injected; elsewhere assertions use ranges.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from config.logging_config import get_logger

# Importing the wrapper applies engine patches at module scope (fixes advantage).
from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.class_features import (
    ClassFeatureEngine, get_feature_table)

from dnd.core.modifiers import AdvantageStatus, DamageType

logger = get_logger(__name__)

ALL_CLASSES = ["barbarian", "bard", "cleric", "druid", "fighter", "monk",
               "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard"]

STR = {"strength": 18, "dexterity": 12, "constitution": 16,
       "intelligence": 10, "wisdom": 12, "charisma": 14}
DEX = {"strength": 10, "dexterity": 18, "constitution": 12,
       "intelligence": 10, "wisdom": 12, "charisma": 10}
WIS = {"strength": 12, "dexterity": 14, "constitution": 14,
       "intelligence": 10, "wisdom": 14, "charisma": 10}
CHA = {"strength": 10, "dexterity": 12, "constitution": 12,
       "intelligence": 10, "wisdom": 12, "charisma": 18}


# ---------------------------------------------------------------------------
# helpers (mirroring tests/combat/test_class_features.py)
# ---------------------------------------------------------------------------

def _sheet(char_id, character_class, scores, level=5, equipment=("Greatsword",),
           features=None, **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": level,
        "ability_scores": dict(scores),
        "hit_points": {"current": 60, "maximum": 60, "temporary": 0},
        "armor_class": 12, "character_class": character_class, "race": "Alethi",
        "background": "Soldier", "equipment": list(equipment),
        "proficiency_bonus": 3,
    }
    if features is not None:
        sheet["features"] = list(features)
    sheet.update(over)
    return sheet


class _Engine:
    """The tiny GameEngine stand-in the sibling combat tests use."""

    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()

    def update_combat_state(self, *a, **k):
        return None


class _FixedDice:
    """A dice roller with scripted results, injected for a deterministic branch."""

    def __init__(self, roll_total=6):
        self._roll = roll_total

    def damage_roll(self, *a, **k):
        return {"total_damage": self._roll}

    def saving_throw(self, *a, **k):
        return {"total": 1}


def _build(specs):
    """Build a wrapper with the named characters. specs: (id, class, scores, equip[, feats])."""
    manager = CharacterManager()
    for spec in specs:
        char_id, character_class, scores, equipment = spec[:4]
        feats = spec[4] if len(spec) > 4 else None
        manager.add_character(_sheet(char_id, character_class, scores,
                                     level=spec[5] if len(spec) > 5 else 5,
                                     equipment=equipment, features=feats))
    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                               character_manager=manager)
    for index, spec in enumerate(specs):
        wrapper.set_entity_position(spec[0], (index, 1))
    return manager, wrapper, dict(wrapper.entities)


def _engine(wrapper, manager, dice=None):
    return ClassFeatureEngine(wrapper, character_manager=manager,
                              combat_state={"round_number": 1,
                                            "combatant_states": {}},
                              dice_roller=dice)


# ===========================================================================
# 0. Every base class has at least one authored feature
# ===========================================================================

class TestTwelveClassCoverage:

    def test_every_base_class_has_a_feature(self):
        logger.info("🧪 All 12 base classes must have >= 1 authored feature")
        table = get_feature_table()
        missing = []
        for character_class in ALL_CLASSES:
            ids = [e["id"] for e in table.for_character(character_class, 20)]
            logger.info(f"   🎖️  {character_class:10s}: {len(ids)} — {', '.join(ids)}")
            if not ids:
                missing.append(character_class)
        assert not missing, f"classes with no authored feature: {missing}"
        logger.info("   ✅ every base class is represented")

    def test_original_seven_are_intact(self):
        logger.info("🧪 Widening must not drop the original seven features")
        ids = {e["id"] for e in get_feature_table().all()}
        original = {"second_wind", "action_surge", "rage", "sneak_attack",
                    "divine_smite", "bardic_inspiration",
                    "channel_divinity_turn_undead"}
        assert original <= ids, f"lost: {original - ids}"
        logger.info(f"   ✅ {len(ids)} features total, original seven present")

    def test_needs_subsystem_is_populated(self):
        logger.info("🧪 The needs_subsystem gap list must be explicit and non-empty")
        payload = json.loads(
            (PROJECT_ROOT / "data" / "rules" / "class_features"
             / "class_features.json").read_text(encoding="utf-8"))
        gaps = payload["_meta"]["needs_subsystem"]
        assert len(gaps) >= 5, "the honest gap list should name the real subsystems"
        blob = json.dumps(gaps).lower()
        for expected in ("wild shape", "ki", "metamagic", "pact magic",
                         "invocation", "spell", "divine intervention"):
            assert expected in blob, f"needs_subsystem should mention {expected!r}"
        for entry in gaps:
            assert entry.get("reason"), f"{entry} needs a one-line reason"
        logger.info(f"   ✅ {len(gaps)} subsystems listed, each with a reason")


# ===========================================================================
# 1. Each NEW effect node executes and produces measured state
# ===========================================================================

class TestNewEffectNodes:

    def test_ability_score_bonus_raises_the_score(self):
        logger.info("🧪 ability_score_bonus must raise the ability SCORE (Primal Champion)")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",),
                                          None, 20)])
        entity = ents["b"]
        before_str = entity.ability_scores.strength.ability_score.score
        before_con = entity.ability_scores.constitution.ability_score.score
        eng = _engine(wrapper, manager)

        result = eng.apply_passives("b")
        assert "primal_champion" in result, result
        assert entity.ability_scores.strength.ability_score.score == before_str + 4
        assert entity.ability_scores.constitution.ability_score.score == before_con + 4
        logger.info(f"   💪 STR {before_str}->{entity.ability_scores.strength.ability_score.score}, "
                    f"CON {before_con}->{entity.ability_scores.constitution.ability_score.score}")

    def test_ac_bonus_raises_armor_class(self):
        logger.info("🧪 ac_bonus must raise Armor Class (Fighter Defense style)")
        manager, wrapper, ents = _build([("f", "Fighter", STR, ("Greatsword",))])
        entity = ents["f"]
        assert entity.equipment.ac_bonus.score == 0
        before_ac = entity.ac_bonus().normalized_score
        eng = _engine(wrapper, manager)

        applied = eng.apply_passives("f")
        assert "fighting_style_defense" in applied, applied
        assert entity.equipment.ac_bonus.score == 1
        assert entity.ac_bonus().normalized_score == before_ac + 1
        logger.info(f"   🛡️  AC {before_ac}->{entity.ac_bonus().normalized_score}")

    def test_speed_bonus_raises_movement(self):
        logger.info("🧪 speed_bonus must raise movement (Barbarian Fast Movement)")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        before = entity.action_economy.movement.normalized_score
        eng = _engine(wrapper, manager)

        applied = eng.apply_passives("b")
        assert "fast_movement" in applied, applied
        assert entity.action_economy.movement.normalized_score == before + 10
        logger.info(f"   🏃 movement {before}->{entity.action_economy.movement.normalized_score}")

    def test_advantage_on_a_saving_throw(self):
        logger.info("🧪 advantage must land ADVANTAGE on the named save (Danger Sense)")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        dex_save = entity.saving_throws.get_saving_throw("dexterity").bonus
        assert dex_save.advantage != AdvantageStatus.ADVANTAGE
        eng = _engine(wrapper, manager)

        applied = eng.apply_passives("b")
        assert "danger_sense" in applied, applied
        assert dex_save.advantage == AdvantageStatus.ADVANTAGE
        # A different save must be untouched.
        con_save = entity.saving_throws.get_saving_throw("constitution").bonus
        assert con_save.advantage != AdvantageStatus.ADVANTAGE
        logger.info("   🎯 advantage on DEX saves, CON saves unaffected")

    def test_advantage_on_attack(self):
        logger.info("🧪 advantage on attack must land ADVANTAGE on the weapon (Steady Aim)")
        manager, wrapper, ents = _build([("r", "Rogue", DEX, ("Dagger",))])
        entity = ents["r"]
        weapon_bonus = entity.equipment.weapon_main_hand.attack_bonus
        assert weapon_bonus.advantage != AdvantageStatus.ADVANTAGE
        eng = _engine(wrapper, manager)

        result = eng.use("r", "steady_aim")
        assert result.success, result.error
        assert weapon_bonus.advantage == AdvantageStatus.ADVANTAGE
        assert eng.is_active("steady_aim", "r")
        logger.info("   🎯 rogue has advantage on the next weapon attack")

    def test_temp_hp_fills_the_pool(self):
        logger.info("🧪 temp_hp must add Temporary Hit Points (Ranger Tireless)")
        # Ranger L10 with WIS 14 (+2): 1d8+2 temp HP. Fixed die => 6+2 = 8.
        manager, wrapper, ents = _build([("ra", "Ranger", WIS, ("Longbow",),
                                          None, 10)])
        entity = ents["ra"]
        assert entity.health.temporary_hit_points.score == 0
        eng = _engine(wrapper, manager, dice=_FixedDice(roll_total=8))

        result = eng.use("ra", "tireless")
        assert result.success, result.error
        # 1d8 (pinned to 6 -> total 8 incl. the +wis the roller ignores) => pool > 0
        assert entity.health.temporary_hit_points.score > 0
        assert eng.is_active("tireless", "ra")
        logger.info(f"   💗 temp HP pool now {entity.health.temporary_hit_points.score}")


# ===========================================================================
# 2. Passives apply and are stripped at end of combat
# ===========================================================================

class TestPassiveLifecycle:

    def test_apply_passives_then_clear_all(self):
        logger.info("🧪 apply_passives must apply, clear_all must strip (no leak to next fight)")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager)

        applied = eng.apply_passives("b")
        # Level-5 Barbarian: Danger Sense + Fast Movement are the passives.
        assert set(applied) >= {"danger_sense", "fast_movement"}, applied
        assert entity.action_economy.movement.normalized_score == 40
        dex_save = entity.saving_throws.get_saving_throw("dexterity").bonus
        assert dex_save.advantage == AdvantageStatus.ADVANTAGE

        eng.clear_all()
        assert eng.active_features("b") == []
        assert entity.action_economy.movement.normalized_score == 30, (
            "a passive speed bonus left on the entity follows them into the next fight")
        assert dex_save.advantage != AdvantageStatus.ADVANTAGE
        logger.info("   🧹 movement back to 30, advantage cleared")

    def test_apply_passives_is_idempotent(self):
        logger.info("🧪 apply_passives twice must not stack the bonus")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager)

        eng.apply_passives("b")
        first = entity.action_economy.movement.normalized_score
        eng.apply_passives("b")          # second call
        assert entity.action_economy.movement.normalized_score == first, (
            "re-applying passives must not double the speed bonus")
        logger.info(f"   ✅ movement stable at {first} across two apply_passives calls")


# ===========================================================================
# 3. A representative ACTIVATED feature per martial class fires in a real turn
# ===========================================================================

def _combat(manager):
    from components.game_engine import GameEngine
    from components.combat.combat_action_resolver import CombatActionResolver

    game_engine = GameEngine()
    # __post_init__ already builds and EQUIPS entities; a second explicit sync
    # would recreate them without their weapons, so we rely on construction.
    wrapper = DnDEngineWrapper(game_engine, manager)
    combat_state = {"combatant_states": {cid: {"hp_current": 40, "hp_max": 40}
                                         for cid in manager.characters},
                    "round_number": 1}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=manager,
                                    combat_state=combat_state)
    return wrapper, resolver, combat_state


class TestActivatedFeaturesFireInATurn:

    def test_paladin_lay_on_hands_heals(self):
        logger.info("🧪 Paladin Lay On Hands must heal in a real turn")
        manager = CharacterManager()
        manager.add_character(_sheet("pal", "Paladin", STR, level=5,
                                     features=["Lay On Hands"]))
        wrapper, resolver, _ = _combat(manager)
        entity = wrapper.entities["pal"]
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("lay_on_hands", manager.characters["pal"])

        from dnd.core.modifiers import DamageType as DT
        entity.health.take_damage(15, DT.SLASHING, entity.uuid)
        before = wrapper.get_entity_current_hp(entity)
        result = resolver.resolve_action({"actor": "pal",
                                          "action_type": "lay_on_hands"})
        after = wrapper.get_entity_current_hp(entity)
        assert result["success"], result.get("error")
        assert result.get("healed", 0) > 0 and after > before
        logger.info(f"   💚 Lay On Hands healed {after - before} HP")

    def test_rogue_steady_aim_grants_advantage(self):
        logger.info("🧪 Rogue Steady Aim must grant attack advantage in a real turn")
        manager = CharacterManager()
        manager.add_character(_sheet("rog", "Rogue", DEX, level=5,
                                     equipment=("Dagger",),
                                     features=["Sneak Attack", "Steady Aim"]))
        wrapper, resolver, cstate = _combat(manager)
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("steady_aim", manager.characters["rog"])

        result = resolver.resolve_action({"actor": "rog",
                                          "action_type": "steady_aim"})
        assert result["success"], result.get("error")
        engine = wrapper.class_feature_engine(combat_state=cstate)
        assert engine.is_active("steady_aim", "rog")
        weapon_bonus = wrapper.entities["rog"].equipment.weapon_main_hand.attack_bonus
        assert weapon_bonus.advantage == AdvantageStatus.ADVANTAGE
        logger.info("   🎯 rogue gained advantage on the next attack")

    def test_ranger_tireless_grants_temp_hp(self):
        logger.info("🧪 Ranger Tireless must grant temp HP in a real turn")
        manager = CharacterManager()
        manager.add_character(_sheet("ran", "Ranger", WIS, level=10,
                                     equipment=("Longbow",),
                                     features=["Tireless"]))
        wrapper, resolver, _ = _combat(manager)
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("tireless", manager.characters["ran"])

        result = resolver.resolve_action({"actor": "ran",
                                          "action_type": "tireless"})
        assert result["success"], result.get("error")
        thp = wrapper.entities["ran"].health.temporary_hit_points.score
        assert thp > 0, "Tireless should add temporary hit points"
        logger.info(f"   💗 Ranger temp HP pool now {thp}")

    def test_sorcerer_innate_sorcery_grants_advantage(self):
        logger.info("🧪 Sorcerer Innate Sorcery must grant attack advantage in a real turn")
        manager = CharacterManager()
        manager.add_character(_sheet("sor", "Sorcerer", CHA, level=5,
                                     equipment=("Dagger",),
                                     features=["Innate Sorcery"]))
        wrapper, resolver, cstate = _combat(manager)
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("innate_sorcery", manager.characters["sor"])

        result = resolver.resolve_action({"actor": "sor",
                                          "action_type": "innate_sorcery"})
        assert result["success"], result.get("error")
        engine = wrapper.class_feature_engine(combat_state=cstate)
        assert engine.is_active("innate_sorcery", "sor")
        logger.info("   🎯 sorcerer's innate magic is active")

    def test_barbarian_reckless_attack_grants_advantage(self):
        logger.info("🧪 Barbarian Reckless Attack must grant attack advantage in a real turn")
        manager = CharacterManager()
        manager.add_character(_sheet("bar", "Barbarian", STR, level=5,
                                     features=["Rage", "Reckless Attack"]))
        wrapper, resolver, cstate = _combat(manager)
        from components.combat.action_registry import is_usable_by
        assert is_usable_by("reckless_attack", manager.characters["bar"])

        result = resolver.resolve_action({"actor": "bar",
                                          "action_type": "reckless_attack"})
        assert result["success"], result.get("error")
        weapon_bonus = wrapper.entities["bar"].equipment.weapon_main_hand.attack_bonus
        assert weapon_bonus.advantage == AdvantageStatus.ADVANTAGE
        logger.info("   🎯 barbarian attacks recklessly with advantage")

    def test_wizard_is_not_offered_martial_features(self):
        logger.info("🧪 A Wizard must not be offered martial class features")
        manager = CharacterManager()
        manager.add_character(_sheet("wiz", "Wizard", CHA, level=10,
                                     equipment=("Dagger",),
                                     features=["Arcane Recovery"]))
        _combat(manager)
        from components.combat.action_registry import is_usable_by
        wizard = manager.characters["wiz"]
        for feature in ("lay_on_hands", "steady_aim", "tireless",
                        "reckless_attack", "innate_sorcery"):
            assert not is_usable_by(feature, wizard), (
                f"Wizard should not be offered {feature}")
        logger.info("   ⛔ Wizard correctly denied every martial feature")


# ===========================================================================
# 4. On-hit extra-damage features authored for casters/martials arm correctly
# ===========================================================================

class TestOnHitExtraDamage:

    def test_cleric_divine_strike_arms_radiant(self):
        logger.info("🧪 Cleric Blessed Strikes: Divine Strike must arm 1d8 radiant")
        manager, wrapper, ents = _build([("c", "Cleric", WIS, ("Mace",), None, 7)])
        eng = _engine(wrapper, manager)
        result = eng.use("c", "blessed_strikes_divine_strike")
        assert result.success, result.error
        equipment = ents["c"].equipment
        assert equipment.extra_attack_damage_dices == [8]
        assert equipment.extra_attack_damage_dices_numbers == [1]
        assert equipment.extra_attack_damage_type[0] == DamageType.RADIANT
        logger.info("   ⚔️ armed 1d8 radiant on the cleric's next hit")

    def test_druid_primal_strike_arms_elemental(self):
        logger.info("🧪 Druid Primal Strike must arm 1d8 fire")
        manager, wrapper, ents = _build([("d", "Druid", WIS, ("Scimitar",), None, 7)])
        eng = _engine(wrapper, manager)
        result = eng.use("d", "primal_strike")
        assert result.success, result.error
        equipment = ents["d"].equipment
        assert equipment.extra_attack_damage_dices == [8]
        assert equipment.extra_attack_damage_type[0] == DamageType.FIRE
        logger.info("   ⚔️ armed 1d8 fire on the druid's next hit")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
