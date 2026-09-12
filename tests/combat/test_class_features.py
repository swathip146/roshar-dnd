"""
`components/combat/class_features.py` reads `data/rules/class_features.json` and
turns "what your class does" — Rage, Sneak Attack, Second Wind, Action Surge,
Divine Smite, Bardic Inspiration, Turn Undead — into MEASURABLE engine state. It
is wired (`CharacterManager.grant_class_features`, `DnDEngineWrapper.
sync_class_features_to_entity` and `class_feature_engine()`), and combat logs show
features synced to entities, but it had ZERO test coverage: nothing had ever
confirmed a rage actually reduces damage or that Second Wind actually heals.

This file treats every docstring as unverified and asserts on OBSERVABLE state
rather than status strings, exactly as `test_standard_actions.py` does:

  * **Second Wind** heals `1d10 + fighter level`, caps at maximum, and is spent —
    a second use in the same rest is refused, then a short rest gives it back.
  * **Action Surge** turns `action_economy.actions` from 1 into 2 — a real extra
    action, not a flag — once per short rest, and only from 2nd level.
  * **Rage** raises `equipment.melee_damage_bonus` by the level-scaled amount and
    HALVES bludgeoning/piercing/slashing (`take_damage(20) -> 10`) while leaving
    fire at 20; it ends on `clear()`, when the barbarian goes a round without
    fighting, and after its 10-round duration.
  * **Sneak Attack** arms extra d6s ONLY when the trigger holds (weapon-level
    advantage, or an ally adjacent to the target on the grid) and NOT otherwise,
    scales one die per two rogue levels, and disarms after a single attack.
  * **Divine Smite** arms 2d8 radiant and EXPENDS a spell slot (the bug this
    suite pins: `use()` used to arm the dice and never pay the slot), and is
    refused once no slot remains.
  * **Bardic Inspiration** hands an ally a scaling die and is limited by the
    bard's Charisma modifier; **Turn Undead** is a Wisdom save that applies
    Frightened only on a failure.

Deterministic where a branch must be forced: the engine rolls through its OWN
`DiceRoller` (a private `random.Random`, not the module `random` the grid uses),
so a fixed-die stub is injected to script a heal amount or a save pass/fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from config.logging_config import get_logger

# Importing the wrapper applies `apply_engine_patches()` at module scope, which
# fixes `Dice._roll_with_advantage`; without it advantage is decorative and the
# Sneak Attack advantage trigger below could not be exercised realistically.
from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.battle_map import BattleMap
from components.combat.tactical_grid import TacticalGrid
from components.combat.class_features import (
    ClassFeatureEngine, get_feature_table, rage_damage_bonus, rage_uses,
    sneak_attack_dice, bardic_die, max_uses)

from dnd.actions import Attack, WeaponSlot
from dnd.core.dice import AttackOutcome
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, DamageType

logger = get_logger(__name__)

# Ability presets. STR for the martials, DEX for the rogue, and the caster stats
# that decide save DCs and use counts.
STR = {"strength": 18, "dexterity": 12, "constitution": 16,
       "intelligence": 10, "wisdom": 12, "charisma": 14}
DEX = {"strength": 10, "dexterity": 18, "constitution": 12,
       "intelligence": 10, "wisdom": 12, "charisma": 10}
CHA = {"strength": 10, "dexterity": 12, "constitution": 12,
       "intelligence": 10, "wisdom": 12, "charisma": 18}
WIS = {"strength": 10, "dexterity": 12, "constitution": 12,
       "intelligence": 10, "wisdom": 18, "charisma": 10}
FEEBLE = {"strength": 4, "dexterity": 4, "constitution": 10,
          "intelligence": 4, "wisdom": 4, "charisma": 4}


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _sheet(char_id, character_class, scores, level=5,
           equipment=("Greatsword",), **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": level,
        "ability_scores": dict(scores),
        "hit_points": {"current": 60, "maximum": 60, "temporary": 0},
        "armor_class": 12, "character_class": character_class, "race": "Alethi",
        "background": "Soldier", "equipment": list(equipment),
        "proficiency_bonus": 3,
    }
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
    """
    A dice roller with scripted results, injected so a branch is deterministic.

    The engine only ever asks it for a damage roll (Second Wind's `1d10+level`)
    or a saving throw (Turn Undead), so those are the two methods scripted; both
    return the dict shape the real `DiceRoller` does.
    """

    def __init__(self, heal_total=8, save_total=1):
        self._heal = heal_total
        self._save = save_total

    def damage_roll(self, *a, **k):
        return {"total_damage": self._heal}

    def saving_throw(self, *a, **k):
        return {"total": self._save}


def _build(specs):
    """
    Build a wrapper with the named characters, one grid square apart on a line.

    `specs` is a list of (char_id, character_class, scores, equipment) tuples.
    Returns (character_manager, wrapper, {char_id: entity}).
    """
    manager = CharacterManager()
    for char_id, character_class, scores, equipment in specs:
        manager.add_character(_sheet(char_id, character_class, scores,
                                     equipment=equipment))
    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                               character_manager=manager)
    for index, (char_id, *_rest) in enumerate(specs):
        wrapper.set_entity_position(char_id, (index, 1))
    return manager, wrapper, dict(wrapper.entities)


def _engine(wrapper, manager, combat_state, grid=None, dice=None):
    """A ClassFeatureEngine wired like `wrapper.class_feature_engine()` builds it,
    but constructed directly so a scripted dice roller can be injected."""
    return ClassFeatureEngine(wrapper, character_manager=manager,
                              combat_state=combat_state, tactical_grid=grid,
                              dice_roller=dice)


def _states(*char_ids, **flags):
    """A `combat_state` with one entry per combatant."""
    return {"round_number": 1,
            "combatant_states": {cid: dict(flags) for cid in char_ids}}


def _states_pair(attacker, target):
    """A hostile pair with no grid — the default Sneak Attack setup where neither
    trigger half (advantage / adjacent ally) holds."""
    return {"round_number": 1,
            "combatant_states": {attacker: {"is_hostile": False},
                                 target: {"is_hostile": True}}}


def _give_weapon_advantage(entity):
    """
    Land advantage where flanking and Reckless Attack do — on the WEAPON's
    persistent `attack_bonus` — which is what `_has_advantage` reads.
    """
    weapon = entity.equipment.weapon_main_hand
    weapon.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(
        name="test_advantage", value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))


@pytest.fixture(autouse=True)
def _reset_event_queue():
    """
    Isolate each test from another's leftover on-hit handlers.

    The engine registers a disarm `EventHandler` on the GLOBAL `EventQueue` for
    every on-hit feature it arms (Sneak Attack, Divine Smite), and only
    `clear_all()` removes it — so a test that arms without ending combat leaks one.
    That matters because `EventQueue.process_event` STOPS at the first handler that
    returns None, and every disarm handler returns None: a single stale handler
    then silently suppresses the live one on the next attack. Clearing the queue
    around each test mirrors the engine-registry reset in
    `tests/combat/conftest.py`.
    """
    from dnd.core.events import EventQueue

    def _clear():
        EventQueue._event_handlers.clear()
        EventQueue._event_handlers_by_trigger.clear()
        EventQueue._event_handlers_by_simple_trigger.clear()
        EventQueue._event_handlers_by_source_entity_uuid.clear()

    _clear()
    yield
    _clear()


# ===========================================================================
# 0. The table itself
# ===========================================================================

class TestFeatureTable:

    def test_all_seven_features_load(self):
        logger.info("🧪 The class-feature table must load every authored feature")
        table = get_feature_table()
        ids = {entry["id"] for entry in table.all()}
        expected = {"second_wind", "action_surge", "rage", "sneak_attack",
                    "divine_smite", "bardic_inspiration",
                    "channel_divinity_turn_undead"}
        assert expected <= ids, f"missing features: {expected - ids}"
        logger.info(f"   📖 loaded {len(ids)} features: {', '.join(sorted(ids))}")

    def test_for_character_filters_by_class_and_level(self):
        logger.info("🧪 for_character must gate on class AND min_level")
        table = get_feature_table()
        fighter_1 = {e["id"] for e in table.for_character("fighter", 1)}
        fighter_2 = {e["id"] for e in table.for_character("fighter", 2)}
        assert "second_wind" in fighter_1, "Second Wind is a 1st-level Fighter feature"
        assert "action_surge" not in fighter_1, "Action Surge is only from 2nd level"
        assert "action_surge" in fighter_2
        assert "rage" not in fighter_2, "a Fighter must not receive a Barbarian feature"
        logger.info("   📖 class/level gating holds for the Fighter")

    def test_scaling_helpers_match_5e(self):
        logger.info("🧪 The scaling helpers must reproduce the 5e tables")
        assert (rage_damage_bonus(1), rage_damage_bonus(9), rage_damage_bonus(16)) == (2, 3, 4)
        assert (rage_uses(1), rage_uses(3), rage_uses(6)) == (2, 3, 4)
        assert [sneak_attack_dice(l) for l in (1, 3, 5, 11)] == [1, 2, 3, 6]
        assert (bardic_die(1), bardic_die(5), bardic_die(10)) == (6, 8, 10)
        logger.info("   📈 rage/sneak/bardic scaling tables verified")


# ===========================================================================
# 1. Second Wind (Fighter) — heals 1d10 + level, once per short rest
# ===========================================================================

class TestSecondWind:

    def test_heals_one_d10_plus_level(self):
        logger.info("🧪 Second Wind must heal within 1d10+level and never fabricate HP")
        manager, wrapper, ents = _build([("f", "Fighter", STR, ("Greatsword",))])
        entity = ents["f"]
        entity.health.take_damage(30, DamageType.SLASHING, entity.uuid)
        before = wrapper.get_entity_current_hp(entity)
        eng = _engine(wrapper, manager, _states("f"))

        result = eng.use("f", "second_wind")
        after = wrapper.get_entity_current_hp(entity)
        assert result.success, result.error
        # A level-5 fighter heals 1d10+5, i.e. somewhere in [6, 15].
        assert 6 <= result.healed <= 15, f"1d10+5 out of range: {result.healed}"
        assert after == before + result.healed
        logger.info(f"   💚 healed {result.healed} ({before}->{after})")

    def test_never_heals_above_maximum(self):
        logger.info("🧪 Second Wind must cap at maximum HP")
        manager, wrapper, ents = _build([("f", "Fighter", STR, ("Greatsword",))])
        entity = ents["f"]
        maximum = wrapper.get_entity_max_hp(entity)
        entity.health.take_damage(3, DamageType.SLASHING, entity.uuid)  # tiny wound
        eng = _engine(wrapper, manager, _states("f"))

        result = eng.use("f", "second_wind")
        assert result.success
        assert result.healed == 3, "a 3-HP wound cannot heal more than 3, whatever the roll"
        assert wrapper.get_entity_current_hp(entity) == maximum
        logger.info(f"   💚 capped: healed only the 3 missing HP (max {maximum})")

    def test_is_spent_and_recharges_on_a_short_rest(self):
        logger.info("🧪 Second Wind is once per short rest, then comes back")
        manager, wrapper, ents = _build([("f", "Fighter", STR, ("Greatsword",))])
        ents["f"].health.take_damage(40, DamageType.SLASHING, ents["f"].uuid)
        eng = _engine(wrapper, manager, _states("f"))

        assert eng.uses_left("f", "second_wind") == 1
        assert eng.use("f", "second_wind").success
        assert eng.uses_left("f", "second_wind") == 0
        blocked = eng.use("f", "second_wind")
        assert blocked.success is False and blocked.error == "no uses remaining"

        manager.short_rest("f", hit_dice_to_spend=0)
        assert eng.uses_left("f", "second_wind") == 1, (
            "a short rest must restore a once-per-short-rest feature")
        logger.info("   ♻️  spent once, refused, then recharged on a short rest")

    def test_a_barbarian_cannot_use_second_wind(self):
        logger.info("🧪 Second Wind must be refused for a non-Fighter")
        manager, wrapper, _ = _build([("b", "Barbarian", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states("b"))
        result = eng.use("b", "second_wind")
        assert result.success is False
        assert "fighter" in result.error.lower()
        logger.info(f"   ⛔ refused: {result.error}")


# ===========================================================================
# 2. Action Surge (Fighter) — a real extra action, once per short rest
# ===========================================================================

class TestActionSurge:

    def test_grants_one_extra_action(self):
        logger.info("🧪 Action Surge must add a REAL extra action to the economy")
        manager, wrapper, ents = _build([("f", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states("f"))
        before = ents["f"].action_economy.actions.normalized_score

        result = eng.use("f", "action_surge")
        after = ents["f"].action_economy.actions.normalized_score
        assert result.success, result.error
        assert after == before + 1, f"actions {before} -> {after}, expected +1"
        assert any(e["type"] == "grant_action" for e in result.events)
        logger.info(f"   ⚡ actions {before} -> {after}")

    def test_is_once_per_short_rest(self):
        logger.info("🧪 Action Surge must be once per short rest")
        manager, wrapper, _ = _build([("f", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states("f"))
        assert eng.use("f", "action_surge").success
        second = eng.use("f", "action_surge")
        assert second.success is False and second.error == "no uses remaining"
        manager.short_rest("f", hit_dice_to_spend=0)
        assert eng.uses_left("f", "action_surge") == 1
        logger.info("   ♻️  spent once, refused, recharged on short rest")

    def test_requires_second_level(self):
        logger.info("🧪 Action Surge must be refused below 2nd level")
        manager = CharacterManager()
        manager.add_character(_sheet("f1", "Fighter", STR, level=1))
        wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                                   character_manager=manager)
        eng = _engine(wrapper, manager, _states("f1"))
        result = eng.use("f1", "action_surge")
        assert result.success is False
        assert "level 2" in result.error
        logger.info(f"   ⛔ refused: {result.error}")


# ===========================================================================
# 3. Rage (Barbarian) — +damage, resistance, ends correctly
# ===========================================================================

class TestRage:

    def test_adds_level_scaled_melee_damage(self):
        logger.info("🧪 Rage must add its level-scaled bonus to melee damage")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager, _states("b"))
        assert entity.equipment.melee_damage_bonus.score == 0

        result = eng.use("b", "rage")
        assert result.success, result.error
        assert entity.equipment.melee_damage_bonus.score == rage_damage_bonus(5) == 2
        logger.info(f"   💪 melee damage bonus 0 -> "
                    f"{entity.equipment.melee_damage_bonus.score}")

    def test_resists_physical_but_not_fire(self):
        logger.info("🧪 Rage must halve B/P/S damage while leaving fire untouched")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager, _states("b"))

        assert entity.health.take_damage(20, DamageType.BLUDGEONING, entity.uuid) == 20
        eng.use("b", "rage")
        assert entity.health.take_damage(20, DamageType.BLUDGEONING, entity.uuid) == 10, (
            "raging must halve bludgeoning damage")
        assert entity.health.take_damage(20, DamageType.FIRE, entity.uuid) == 20, (
            "Rage grants no resistance to fire")
        logger.info("   🛡️  bludgeoning 20->10, fire stays 20")

    def test_clear_ends_the_rage(self):
        logger.info("🧪 clear() must remove BOTH the damage bonus and the resistance")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager, _states("b"))
        eng.use("b", "rage")
        assert eng.is_active("rage", "b")

        assert eng.clear("rage", "b") is True
        assert eng.is_active("rage", "b") is False
        assert entity.equipment.melee_damage_bonus.score == 0
        assert entity.health.take_damage(20, DamageType.BLUDGEONING, entity.uuid) == 20
        logger.info("   ⏹️  bonus back to 0, full bludgeoning damage restored")

    def test_ends_when_the_barbarian_goes_quiet(self):
        logger.info("🧪 Rage must end after a round with no attack and no damage taken")
        manager, wrapper, _ = _build([("b", "Barbarian", STR, ("Greatsword",))])
        combat_state = _states("b", attacked_this_round=True,
                               took_damage_this_round=False)
        eng = _engine(wrapper, manager, combat_state)
        eng.use("b", "rage")

        assert eng.tick_round() == [], "a barbarian who attacked keeps raging"
        assert eng.is_active("rage", "b")
        combat_state["combatant_states"]["b"]["attacked_this_round"] = False
        ended = eng.tick_round()
        assert ("rage", "b") in ended, "a quiet round must end the rage"
        assert eng.is_active("rage", "b") is False
        logger.info("   😤 rage persisted through the fight, ended on the quiet round")

    def test_ends_after_its_ten_round_duration(self):
        logger.info("🧪 Rage must lapse after its 10-round duration")
        manager, wrapper, _ = _build([("b", "Barbarian", STR, ("Greatsword",))])
        # Keep it 'fighting' each round so only the duration can end it.
        eng = _engine(wrapper, manager, _states("b", attacked_this_round=True))
        eng.use("b", "rage")
        ended_on = None
        for round_index in range(1, 12):
            if eng.tick_round():
                ended_on = round_index
                break
        assert ended_on == 10, f"rage should end on round 10, ended on {ended_on}"
        logger.info(f"   ⏳ rage ended on round {ended_on}")

    def test_use_count_scales_with_level(self):
        logger.info("🧪 A higher-level barbarian must have more rages")
        for level, expected in ((1, 2), (3, 3), (6, 4)):
            manager = CharacterManager()
            manager.add_character(_sheet("b", "Barbarian", STR, level=level))
            wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                                       character_manager=manager)
            eng = _engine(wrapper, manager, _states("b"))
            assert eng.uses_left("b", "rage") == expected, (
                f"level {level} barbarian: expected {expected} rages")
        logger.info("   🔥 2 rages at L1, 3 at L3, 4 at L6")


# ===========================================================================
# 4. Sneak Attack (Rogue) — conditional, scaling, once per turn
# ===========================================================================

class TestSneakAttack:

    def test_not_offered_without_advantage_or_an_adjacent_ally(self):
        logger.info("🧪 Sneak Attack must NOT be available with neither trigger half")
        manager, wrapper, _ = _build([("r", "Rogue", DEX, ("Dagger",)),
                                      ("foe", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager,
                      _states_pair("r", "foe"))
        offered = [e["id"] for e in eng.on_hit_features("r", "foe")]
        assert "sneak_attack" not in offered, (
            "with no advantage and no adjacent ally the trigger must be false")
        assert eng.trigger_holds(get_feature_table().get("sneak_attack"),
                                 "r", "foe") is False
        logger.info("   🗡️  correctly withheld — no advantage, no ally")

    def test_advantage_enables_it(self):
        logger.info("🧪 Weapon-level advantage must satisfy the Sneak Attack trigger")
        manager, wrapper, ents = _build([("r", "Rogue", DEX, ("Dagger",)),
                                         ("foe", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states_pair("r", "foe"))
        _give_weapon_advantage(ents["r"])
        assert eng._has_advantage("r") is True
        assert "sneak_attack" in [e["id"] for e in eng.on_hit_features("r", "foe")]
        logger.info("   🗡️  advantage on the weapon enables Sneak Attack")

    def test_an_adjacent_ally_enables_it(self):
        logger.info("🧪 An ally within 5 ft of the target must satisfy the trigger")
        manager, wrapper, _ = _build([("r", "Rogue", DEX, ("Dagger",)),
                                      ("ally", "Fighter", STR, ("Greatsword",)),
                                      ("foe", "Fighter", STR, ("Greatsword",))])
        wrapper.set_entity_position("r", (0, 0))
        wrapper.set_entity_position("foe", (5, 5))
        wrapper.set_entity_position("ally", (5, 6))   # chebyshev 1 from the foe
        grid = TacticalGrid(BattleMap(name="t", rows=["........"] * 8),
                            dnd_wrapper=wrapper)
        combat_state = {"combatant_states": {
            "r": {"is_hostile": False}, "ally": {"is_hostile": False},
            "foe": {"is_hostile": True}}}
        eng = _engine(wrapper, manager, combat_state, grid=grid)

        assert eng._has_advantage("r") is False, "no advantage in this setup"
        assert eng._ally_adjacent_to("r", "foe") is True
        assert "sneak_attack" in [e["id"] for e in eng.on_hit_features("r", "foe")]

        wrapper.set_entity_position("ally", (0, 1))   # ally walks away
        assert eng._ally_adjacent_to("r", "foe") is False
        assert "sneak_attack" not in [e["id"] for e in eng.on_hit_features("r", "foe")]
        logger.info("   🗡️  enabled while the ally flanks, withdrawn when it leaves")

    def test_arms_level_scaled_weapon_dice(self):
        logger.info("🧪 Sneak Attack must arm sneak_attack_dice d6 of the weapon's type")
        manager, wrapper, ents = _build([("r", "Rogue", DEX, ("Dagger",)),
                                         ("foe", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states_pair("r", "foe"))
        result = eng.use("r", "sneak_attack")
        assert result.success, result.error
        equipment = ents["r"].equipment
        assert sneak_attack_dice(5) == 3          # a level-5 rogue: 3d6
        assert equipment.extra_attack_damage_dices == [6]
        assert equipment.extra_attack_damage_dices_numbers == [3]
        assert equipment.extra_attack_damage_type[0] == DamageType.PIERCING, (
            "a Dagger deals piercing, and Sneak Attack rides the weapon's type")
        logger.info(f"   🗡️  armed {equipment.extra_attack_damage_dices_numbers[0]}"
                    f"d6 piercing")

    def test_disarms_after_a_single_attack(self, monkeypatch):
        logger.info("🧪 Sneak Attack dice must come off after ONE attack (once per turn)")
        import random
        # dnd_engine rolls through the module `random`; pin every die mid-range so
        # the rogue lands a decisive HIT (not a nat-1 crit-miss) and the ATTACK
        # event reaches the EFFECT phase the disarm handler listens on.
        monkeypatch.setattr(random, "randint", lambda a, b: min(b, 15))
        manager, wrapper, ents = _build([("r", "Rogue", DEX, ("Dagger",)),
                                         ("foe", "Fighter", STR, ("Greatsword",))])
        wrapper.set_entity_position("r", (0, 0))
        wrapper.set_entity_position("foe", (1, 0))
        eng = _engine(wrapper, manager, _states_pair("r", "foe"))
        eng.use("r", "sneak_attack")
        rogue = ents["r"]
        assert rogue.equipment.extra_attack_damage_dices == [6]

        event = Attack(source_entity_uuid=rogue.uuid,
                       target_entity_uuid=ents["foe"].uuid,
                       weapon_slot=WeaponSlot.MAIN_HAND).apply()
        assert getattr(event, "attack_outcome", None) in (
            AttackOutcome.HIT, AttackOutcome.CRIT), "setup must land a hit"
        assert rogue.equipment.extra_attack_damage_dices == [], (
            "the armed dice must be disarmed after the attack resolves")
        assert eng.is_active("sneak_attack", "r") is False
        logger.info("   🗡️  dice armed, spent on one attack, then gone")


# ===========================================================================
# 5. Divine Smite (Paladin) — 2d8 radiant, expends a spell slot
# ===========================================================================

def _paladin_with_slots(slots):
    manager = CharacterManager()
    manager.add_character(_sheet("p", "Paladin", STR, equipment=("Greatsword",)))
    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                               character_manager=manager)
    wrapper.set_entity_position("p", (0, 1))
    manager.characters["p"].spell_slots = slots
    return manager, wrapper


class TestDivineSmite:

    def test_arms_two_d8_radiant(self):
        logger.info("🧪 Divine Smite must arm 2d8 radiant on a hit")
        manager, wrapper = _paladin_with_slots({1: {"current": 1, "maximum": 1}})
        eng = _engine(wrapper, manager, _states("p"))
        result = eng.use("p", "divine_smite")
        assert result.success, result.error
        equipment = wrapper.entities["p"].equipment
        assert equipment.extra_attack_damage_dices == [8]
        assert equipment.extra_attack_damage_dices_numbers == [2]
        assert equipment.extra_attack_damage_type[0] == DamageType.RADIANT
        logger.info("   ✨ armed 2d8 radiant")

    def test_expends_a_spell_slot(self):
        logger.info("🧪 Divine Smite must expend a spell slot (the bug this pins)")
        manager, wrapper = _paladin_with_slots({1: {"current": 2, "maximum": 2}})
        eng = _engine(wrapper, manager, _states("p"))
        slots = manager.characters["p"].spell_slots

        assert eng.use("p", "divine_smite").success
        assert slots[1]["current"] == 1, "using Divine Smite must burn a slot"
        assert eng.use("p", "divine_smite").success
        assert slots[1]["current"] == 0
        logger.info("   🔮 two smites burned two slots (2 -> 1 -> 0)")

    def test_refused_with_no_spell_slot(self):
        logger.info("🧪 Divine Smite must be refused once no slot remains")
        manager, wrapper = _paladin_with_slots({1: {"current": 0, "maximum": 1}})
        eng = _engine(wrapper, manager, _states("p"))
        assert eng.trigger_holds(get_feature_table().get("divine_smite"), "p") is False
        result = eng.use("p", "divine_smite")
        assert result.success is False
        assert "spell slot" in result.error
        logger.info(f"   ⛔ refused: {result.error}")

    def test_scales_with_the_expended_slot_level(self):
        logger.info("🧪 Divine Smite should deal 3d8 from a 2nd-level slot")
        manager, wrapper = _paladin_with_slots({2: {"current": 1, "maximum": 1}})
        eng = _engine(wrapper, manager, _states("p"))
        eng.use("p", "divine_smite")
        count = wrapper.entities["p"].equipment.extra_attack_damage_dices_numbers[0]
        assert count == 3, f"a 2nd-level slot should smite for 3d8, got {count}d8"


# ===========================================================================
# 6. Bardic Inspiration (Bard) — a scaling die, limited by Charisma
# ===========================================================================

class TestBardicInspiration:

    def test_hands_an_ally_a_scaling_die(self):
        logger.info("🧪 Bardic Inspiration must give the ally a level-scaled die")
        manager, wrapper, _ = _build([("bard", "Bard", CHA, ("Dagger",)),
                                      ("ally", "Fighter", STR, ("Greatsword",))])
        combat_state = _states("bard", "ally")
        eng = _engine(wrapper, manager, combat_state)

        result = eng.use("bard", "bardic_inspiration", target="ally")
        assert result.success, result.error
        dice = combat_state["combatant_states"]["ally"].get("inspiration_dice")
        assert bardic_die(5) == 8                  # a level-5 bard: d8
        assert dice == [8], f"expected a d8 for the ally, got {dice}"
        logger.info(f"   🎵 ally holds an inspiration d{dice[0]}")

    def test_use_count_is_the_charisma_modifier(self):
        logger.info("🧪 Bardic Inspiration uses must equal the Charisma modifier")
        manager, wrapper, _ = _build([("bard", "Bard", CHA, ("Dagger",)),
                                      ("ally", "Fighter", STR, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states("bard", "ally"))
        # CHA 18 -> +4.
        assert eng.uses_left("bard", "bardic_inspiration") == 4
        assert max_uses(get_feature_table().get("bardic_inspiration"),
                        manager.characters["bard"]) == 4
        eng.use("bard", "bardic_inspiration", target="ally")
        assert eng.uses_left("bard", "bardic_inspiration") == 3
        logger.info("   🎵 4 uses (CHA +4), 3 left after one")


# ===========================================================================
# 7. Channel Divinity: Turn Undead (Cleric) — save, Frightened on a failure
# ===========================================================================

class TestTurnUndead:

    def test_a_failed_save_frightens_the_target(self):
        logger.info("🧪 Turn Undead must apply Frightened when the save fails")
        manager, wrapper, ents = _build([("cleric", "Cleric", WIS, ("Mace",)),
                                         ("undead", "Fighter", FEEBLE, ("Greatsword",))])
        # Script the save low so the branch is deterministic.
        eng = _engine(wrapper, manager, _states("cleric", "undead"),
                      dice=_FixedDice(save_total=1))
        result = eng.use("cleric", "channel_divinity_turn_undead", target="undead")
        assert result.success, result.error
        event = result.events[0]
        assert event["failed"] is True
        assert "Frightened" in (ents["undead"].active_conditions or {}), (
            "a failed save must land the Frightened condition")
        logger.info(f"   😱 save {event['roll']} < DC {event['dc']}: Frightened applied")

    def test_a_successful_save_applies_nothing(self):
        logger.info("🧪 Turn Undead must leave a target that saves untouched")
        manager, wrapper, ents = _build([("cleric", "Cleric", WIS, ("Mace",)),
                                         ("undead", "Fighter", FEEBLE, ("Greatsword",))])
        eng = _engine(wrapper, manager, _states("cleric", "undead"),
                      dice=_FixedDice(save_total=99))
        result = eng.use("cleric", "channel_divinity_turn_undead", target="undead")
        assert result.success
        assert result.events[0]["failed"] is False
        assert "Frightened" not in (ents["undead"].active_conditions or {})
        logger.info("   🛡️  save made: no condition applied")

    def test_no_target_does_not_crash(self):
        logger.info("🧪 Turn Undead with no target must resolve cleanly")
        manager, wrapper, _ = _build([("cleric", "Cleric", WIS, ("Mace",))])
        eng = _engine(wrapper, manager, _states("cleric"))
        result = eng.use("cleric", "channel_divinity_turn_undead", target="")
        assert result.success
        assert result.events[0]["target"] == ""
        logger.info("   ✅ handled a missing target without a roll")


# ===========================================================================
# 8. End-of-combat cleanup — modifiers live on the entity, which outlives combat
# ===========================================================================

class TestClearAll:

    def test_clear_all_wipes_every_active_modifier(self):
        logger.info("🧪 clear_all must strip every feature modifier at combat end")
        manager, wrapper, ents = _build([("b", "Barbarian", STR, ("Greatsword",))])
        entity = ents["b"]
        eng = _engine(wrapper, manager, _states("b"))
        eng.use("b", "rage")
        assert entity.equipment.melee_damage_bonus.score == 2

        eng.clear_all()
        assert eng.active_features("b") == []
        assert entity.equipment.melee_damage_bonus.score == 0, (
            "a rage left on the entity would follow the barbarian into the next fight")
        assert entity.health.take_damage(20, DamageType.BLUDGEONING, entity.uuid) == 20
        logger.info("   🧹 rage bonus and resistance both cleared")
