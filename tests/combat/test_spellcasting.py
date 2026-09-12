"""
5e SPELLCASTING: 319 SRD spells were indexed and ZERO were castable.

THE BUG, IN THREE LAYERS
------------------------
1. NOTHING CONSUMED `spell_slots`. `CharacterData.spell_slots` has existed all
   along as `{level: {"current": N, "maximum": N}}`, and grep showed it read only
   for the analytics summary ("spell_slots_remaining: 'high'"). A wizard could
   have cast Fireball every round of every day forever — except they could not
   cast it at all, because:

2. THERE WAS NO `cast` ACTION. ACTION_REGISTRY held attack/dash/dodge/move plus
   five Roshar surges. Casting was not on the player menu and was not in the NPC
   AI's option list, so the choice never existed.

3. THE ENGINE HAS NO SPELL SYSTEM to delegate to. `import dnd.spells` fails and
   `dnd.actions` exports exactly `Attack` and `Move`. So this had to be built at
   our seam, and it reuses `ManeuverExecutor` (the Surgebinding automation-tree
   interpreter) rather than growing a second effect engine.

WHAT THESE TESTS GUARD
----------------------
Assertions are on OUTCOMES — HP actually dropped, a slot count actually fell, the
save branch actually differed — not on attribute values, because the surge bugs
all passed unit tests that constructed the action directly with everything supplied.

Two failure modes get their own classes:

  * OFFERABILITY. `cast_spell` needs a `spell_name`, and an action needing a
    parameter nothing supplies is filtered out of BOTH menus by `is_offerable()`.
    That exact bug made 4 of 5 Surges unplayable while every unit test passed.
  * THE SILENT ZERO. A spell whose mechanics live only in prose (Bless, Wish,
    Hold Person — 243 of the 319) must report `needs_adjudication` and spend NO
    slot. It must never report success having dealt 0. The project's rule comes
    from `_meta.correction` in surgebinding.json: invented numbers here were
    "plausible and wrong".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.action_registry import (ACTION_REGISTRY, is_offerable,
                                               offerable_actions,
                                               param_defaults,
                                               required_caller_params,
                                               unusable_reason, usable_actions)
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.spell_compiler import compile_spell
from components.combat.spellcasting import (MAX_SPELL_LEVEL,
                                            ConcentrationTracker,
                                            SpellcastingService,
                                            SpellSlotLedger,
                                            spellcasting_ability,
                                            spellcasting_stats)
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.srd_rules import get_srd_rules


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, character_class="Wizard", **over):
    """A level-5 caster with INT 18 / WIS 16 unless overridden."""
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 10, "dexterity": 14, "constitution": 12,
                           "intelligence": 18, "wisdom": 16, "charisma": 8},
        # Deep pool so damage tests never tip into death saves.
        "hit_points": {"current": 200, "maximum": 200, "temporary": 0},
        "armor_class": 13, "character_class": character_class, "race": "Human",
        "background": "Sage", "proficiency_bonus": 3, "equipment": ["Dagger"],
    }
    sheet.update(over)
    return sheet


@pytest.fixture
def table():
    """A wizard, a cleric, a fighter (non-caster) and a target."""
    from components.combat.tactical_grid import TacticalGrid

    TacticalGrid._clear_tiles()
    manager = CharacterManager()
    manager.add_character(_sheet(
        "Wiz",
        spell_slots={1: {"current": 4, "maximum": 4},
                     2: {"current": 3, "maximum": 3},
                     3: {"current": 2, "maximum": 2}},
        spells_known=["Fireball", "Fire Bolt", "Cure Wounds", "Bless",
                      "Wish", "Magic Missile", "Flaming Sphere",
                      "Vampiric Touch"]))
    manager.add_character(_sheet(
        "Cleric", character_class="Cleric",
        spell_slots={1: {"current": 3, "maximum": 3}},
        spells_known=["Cure Wounds", "Sacred Flame", "Guiding Bolt",
                      "Hold Person"]))
    manager.add_character(_sheet("Grunt", character_class="Fighter",
                                 spells_known=[]))
    manager.add_character(_sheet("Target", character_class="Fighter"))

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    for index, char_id in enumerate(["Wiz", "Cleric", "Grunt", "Target"]):
        wrapper.set_entity_position(char_id, (index, 0))
    wrapper.refresh_senses()

    combat_state = {"combatant_states": {
        char_id: {"hp_current": 200, "hp_max": 200,
                  "is_hostile": char_id in ("Grunt", "Target")}
        for char_id in ["Wiz", "Cleric", "Grunt", "Target"]}}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                   character_manager=manager,
                                   combat_state=combat_state)
    yield resolver, wrapper, manager
    TacticalGrid._clear_tiles()


def _hp(wrapper, char_id):
    entity = wrapper.entities[char_id]
    con = entity.ability_scores.constitution.modifier
    return entity.health.get_total_hit_points(con)


def _wound(wrapper, char_id, amount):
    from dnd.core.modifiers import DamageType

    entity = wrapper.entities[char_id]
    entity.health.take_damage(amount, DamageType.SLASHING, entity.uuid)


def _cast(resolver, wrapper, actor, target="Target", **params):
    """
    Resolve a cast the way the GAME does — through CombatActionResolver.

    The action economy is reset first so a test can cast repeatedly; the economy
    itself has its own test below.
    """
    wrapper.entities[actor].action_economy.reset_all_costs()
    return resolver.resolve_action({"actor": actor, "action_type": "cast_spell",
                                    "target": target, **params})


def _slots(manager, char_id):
    return {level: data["current"]
            for level, data in manager.characters[char_id].spell_slots.items()}


# ---------------------------------------------------------------------------
# 1. Spellcasting stats
# ---------------------------------------------------------------------------

class TestSpellcastingStats:
    """
    DC = 8 + proficiency + ability modifier; attack = proficiency + modifier.

    Nothing computed either number anywhere in the codebase before this.
    """

    @pytest.mark.parametrize("character_class,ability", [
        ("Wizard", "intelligence"),
        ("Cleric", "wisdom"),
        ("Druid", "wisdom"),
        ("Bard", "charisma"),
        ("Sorcerer", "charisma"),
        ("Warlock", "charisma"),
        ("Paladin", "charisma"),
    ])
    def test_each_class_casts_with_its_own_ability(self, character_class,
                                                   ability):
        assert spellcasting_ability(character_class) == ability

    def test_a_wizards_dc_uses_intelligence_not_wisdom(self, table):
        """
        INT 18 (+4) and WIS 16 (+3) differ deliberately, so a DC computed off the
        wrong ability is visible: 15 vs 14. Using "the highest modifier" or a
        fixed ability would pass a same-score fixture and fail in play.
        """
        _, _, manager = table
        stats = spellcasting_stats(manager.characters["Wiz"], "Wiz")
        assert stats.ability == "intelligence"
        assert stats.save_dc == 8 + 3 + 4 == 15
        assert stats.attack_bonus == 3 + 4 == 7

    def test_a_clerics_dc_uses_wisdom(self, table):
        _, _, manager = table
        stats = spellcasting_stats(manager.characters["Cleric"], "Cleric")
        assert stats.ability == "wisdom"
        assert stats.save_dc == 8 + 3 + 3 == 14

    def test_a_non_caster_gets_no_dc_rather_than_a_plausible_one(self, table):
        """
        A fighter must get None, NOT 8 + proficiency + 0 = 11.

        A number here is the dangerous answer: it makes "cast Fireball" look
        computable, and something downstream would use it. The same class of bug
        as `AbilityConfig(score=...)` being silently ignored so every ability
        score sat at 10.
        """
        _, _, manager = table
        stats = spellcasting_stats(manager.characters["Grunt"], "Grunt")
        assert stats.is_caster is False
        assert stats.save_dc is None
        assert stats.attack_bonus is None

    def test_the_dc_the_engine_actually_rolls_against_is_the_computed_one(
            self, table):
        """
        The DC must reach the save, not just the stats object.

        Asserted on the emitted save event, because a DC that is computed and then
        discarded is precisely bug 2.1 in this project: the skill pipeline
        discarded the requested DC, so difficulty had no effect on outcomes.
        """
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz", spell_name="Fireball")
        saves = [e for e in result["events"] if e["type"] == "save"]
        assert saves, result
        assert saves[0]["dc"] == 15


# ---------------------------------------------------------------------------
# 2. Slots
# ---------------------------------------------------------------------------

class TestSlotSpending:
    """`spell_slots` had no consumer at all. These assert the count MOVES."""

    def test_casting_a_third_level_spell_spends_a_third_level_slot(self, table):
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        result = _cast(resolver, wrapper, "Wiz", spell_name="Fireball")
        after = _slots(manager, "Wiz")

        assert result["success"] is True, result
        assert after[3] == before[3] - 1, f"{before} -> {after}"
        assert after[1] == before[1], "a 3rd-level spell must not eat a 1st slot"

    def test_a_cantrip_spends_nothing(self, table):
        """Fire Bolt is level 0. Three casts, zero slots."""
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        for _ in range(3):
            result = _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
            assert result["success"] is True, result
            assert result["slot_level"] == 0
        assert _slots(manager, "Wiz") == before

    def test_a_first_level_spell_upcasts_into_a_higher_slot_when_needed(
            self, table):
        """
        5e lets a level-1 spell burn a level-3 slot. Refusing that would tell a
        wizard with only 3rd-level slots left that they cannot cast Cure Wounds.
        """
        resolver, wrapper, manager = table
        character = manager.characters["Wiz"]
        character.spell_slots[1]["current"] = 0
        character.spell_slots[2]["current"] = 0

        _wound(wrapper, "Target", 40)
        result = _cast(resolver, wrapper, "Wiz", spell_name="Cure Wounds")
        assert result["success"] is True, result
        assert result["slot_level"] == 3
        assert _slots(manager, "Wiz")[3] == 1

    def test_upcasting_scales_the_effect_from_the_srd_table(self):
        """
        Fireball at 5th level is 10d6, not 8d6. The SRD gives the whole table;
        reading only row "3" would silently under-report by 2d6.
        """
        srd = get_srd_rules()
        low = compile_spell(srd.spell("Fireball"), slot_level=3)
        high = compile_spell(srd.spell("Fireball"), slot_level=5)

        def dice(compiled):
            save = compiled.automation[0]["effects"][0]
            return save["fail"][0]["damage"]

        assert dice(low) == "8d6"
        assert dice(high) == "10d6"

    def test_no_slot_left_is_a_clean_refusal_with_a_reason(self, table):
        """
        Out of slots must return a result explaining why — not raise, and not
        report a successful cast that did nothing.
        """
        resolver, wrapper, manager = table
        manager.characters["Wiz"].spell_slots[3]["current"] = 0

        result = _cast(resolver, wrapper, "Wiz", spell_name="Fireball")
        assert result["success"] is False
        assert "slot" in (result.get("error", "") + result["description"]).lower()
        assert result["damage"] == 0

    def test_exhausting_slots_stops_the_spell_after_exactly_the_right_count(
            self, table):
        """
        Two 3rd-level slots means two Fireballs and then a refusal. Off-by-one in
        either direction is invisible without counting.
        """
        resolver, wrapper, manager = table
        outcomes = [_cast(resolver, wrapper, "Wiz", spell_name="Fireball")
                    for _ in range(3)]
        assert [o["success"] for o in outcomes] == [True, True, False]
        assert _slots(manager, "Wiz")[3] == 0

    def test_a_refused_cast_spends_no_slot(self, table):
        """
        The resource must not leak. A refusal that still debits is worse than a
        crash, because the player loses the slot and never learns why.
        """
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        result = _cast(resolver, wrapper, "Wiz", spell_name="Bless")
        assert result["success"] is False
        assert _slots(manager, "Wiz") == before

    def test_a_string_keyed_slot_table_still_works(self, table):
        """
        `to_dict()` stringifies the slot keys for JSON and `from_dict` restores
        ints — but a save written by hand, or JSON coming back from the session
        store, can leave strings. A ledger that silently saw no slots would report
        "no slots remaining" for a full wizard.
        """
        _, _, manager = table
        character = manager.characters["Wiz"]
        character.spell_slots = {"3": {"current": 2, "maximum": 2}}

        ledger = SpellSlotLedger(manager)
        assert ledger.available("Wiz") == {3: 2}
        assert ledger.spend("Wiz", 3).spent is True
        assert character.spell_slots["3"]["current"] == 1

    def test_there_is_no_tenth_level_slot(self, table):
        _, _, manager = table
        spend = SpellSlotLedger(manager).spend("Wiz", MAX_SPELL_LEVEL + 1)
        assert spend.spent is False
        assert "no level 10" in spend.reason


# ---------------------------------------------------------------------------
# 3. Effects actually happen
# ---------------------------------------------------------------------------

class TestSaveBasedSpellBranches:
    """
    Fireball's `dc_success: "half"` is the most common spell mechanic in the SRD
    (92 of 319 spells carry a `dc`). Both branches must exist and DIFFER.
    """

    def test_a_failed_save_takes_full_damage_and_hp_drops(self, table):
        resolver, wrapper, _ = table
        before = _hp(wrapper, "Target")
        # 40 casts against a DEX +2 target guarantees at least one failure.
        for _ in range(40):
            wrapper.entities["Wiz"].__dict__.pop("_unused", None)
            resolver.character_manager.characters["Wiz"].spell_slots[3][
                "current"] = 2
            result = _cast(resolver, wrapper, "Wiz", spell_name="Fireball")
            failed = [e for e in result["events"]
                      if e["type"] == "save" and not e["passed"]]
            if failed:
                assert result["damage"] > 0, result
                assert _hp(wrapper, "Target") < before, "HP did not drop"
                return
        pytest.fail("no failed save in 40 Fireballs — the save is not being rolled")

    def test_a_successful_save_takes_half_not_zero(self, table):
        """
        `dc_success: "half"`. A success branch that dealt 0 would look like a
        working spell and quietly halve Fireball's real output.
        """
        resolver, wrapper, manager = table
        for _ in range(60):
            manager.characters["Wiz"].spell_slots[3]["current"] = 2
            result = _cast(resolver, wrapper, "Wiz", spell_name="Fireball")
            saves = [e for e in result["events"] if e["type"] == "save"]
            if saves and saves[0]["passed"]:
                halved = [e for e in result["events"]
                          if e["type"] == "damage" and e.get("multiplier")]
                assert halved, f"a made save dealt no halved damage: {result}"
                assert result["damage"] > 0, "a made save dealt zero"
                return
        pytest.fail("no successful save in 60 Fireballs")

    def test_the_two_branches_are_not_the_same_amount(self):
        """
        Compiled shape check: the success branch must carry a 0.5 multiplier. If
        both branches rolled the same expression with no multiplier, saving would
        be pointless and no HP assertion would ever notice.
        """
        compiled = compile_spell(get_srd_rules().spell("Fireball"), slot_level=3)
        save = compiled.automation[0]["effects"][0]
        assert save["fail"][0].get("multiplier") in (None, 1)
        assert save["success"][0]["multiplier"] == 0.5

    def test_a_save_that_negates_deals_nothing_on_a_success(self):
        """
        `dc_success: "none"` (Sacred Flame) means a made save takes NOTHING. The
        opposite error to the one above, and equally invisible.
        """
        compiled = compile_spell(get_srd_rules().spell("Sacred Flame"),
                                 slot_level=0, caster_level=5)
        save = compiled.automation[0]["effects"][0]
        assert save["stat"] == "dexterity"
        assert save["success"] == []
        assert save["fail"][0]["damage"] == "2d8"


class TestAttackRollSpells:
    """
    A spell attack is proficiency + spellcasting modifier vs AC — NOT the
    inherited maneuver `attack` node, which swings the actor's MAIN_HAND weapon.
    For a wizard that would roll a dagger's bonus and apply a dagger's damage: a
    plausible number that is not the spell's.
    """

    def test_a_hit_deals_the_spells_damage_and_hp_drops(self, table):
        resolver, wrapper, _ = table
        before = _hp(wrapper, "Target")
        for _ in range(40):
            result = _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
            attacks = [e for e in result["events"]
                       if e["type"] == "spell_attack"]
            assert attacks, f"no spell attack rolled: {result}"
            if attacks[0]["hit"]:
                assert result["damage"] > 0
                assert _hp(wrapper, "Target") < before
                return
        pytest.fail("40 Fire Bolts never hit AC 15 at +7 — the bonus is wrong")

    def test_a_miss_deals_nothing(self, table):
        resolver, wrapper, _ = table
        for _ in range(40):
            before = _hp(wrapper, "Target")
            result = _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
            attacks = [e for e in result["events"] if e["type"] == "spell_attack"]
            if not attacks[0]["hit"]:
                assert result["damage"] == 0
                assert _hp(wrapper, "Target") == before
                return
        pytest.fail("40 Fire Bolts never missed")

    def test_the_roll_is_compared_against_the_targets_real_ac(self, table):
        """
        AC must come from the engine (armour, dex cap, modifiers), not from
        `10 + dex`. `DnDEngineWrapper.execute_attack()` derived it by hand that
        way and would have been blind to cover and Shardplate.
        """
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
        attack = [e for e in result["events"] if e["type"] == "spell_attack"][0]
        engine_ac = int(wrapper.entities["Target"].ac_bonus(
            wrapper.entities["Wiz"].uuid).normalized_score)
        assert attack["ac"] == engine_ac

    def test_a_cantrips_damage_scales_on_caster_level(self):
        """
        Fire Bolt is 1d10 at level 1 and 2d10 at level 5. Defaulting to row "1"
        would under-report a level-17 wizard by 3d10.
        """
        srd = get_srd_rules()
        assert _cantrip_dice(srd, "Fire Bolt", 1) == "1d10"
        assert _cantrip_dice(srd, "Fire Bolt", 5) == "2d10"
        assert _cantrip_dice(srd, "Fire Bolt", 17) == "4d10"


def _cantrip_dice(srd, name, caster_level):
    compiled = compile_spell(srd.spell(name), caster_level=caster_level)
    attack = compiled.automation[0]["effects"][0]
    return attack["hit"][0]["damage"]


class TestHealingSpells:
    """`heal_at_slot_level` exists on 10 SRD spells and had no reader."""

    def test_cure_wounds_actually_restores_hit_points(self, table):
        resolver, wrapper, _ = table
        _wound(wrapper, "Target", 40)
        before = _hp(wrapper, "Target")

        result = _cast(resolver, wrapper, "Cleric", spell_name="Cure Wounds")
        after = _hp(wrapper, "Target")

        assert result["success"] is True, result
        assert after > before, f"HP did not rise: {before} -> {after}"
        assert result["healing"] == after - before

    def test_the_healing_includes_the_spellcasting_modifier(self, table):
        """
        "1d8 + MOD". The cleric has WIS 16 (+3), so healing is 4..11 — never 1,
        which is what dropping the modifier (or letting `{mod}` reach the dice
        parser) would allow.
        """
        resolver, wrapper, manager = table
        for _ in range(12):
            manager.characters["Cleric"].spell_slots[1]["current"] = 3
            _wound(wrapper, "Target", 60)
            result = _cast(resolver, wrapper, "Cleric",
                           spell_name="Cure Wounds")
            assert result["success"] is True, result
            assert 4 <= result["healing"] <= 11, result

    def test_healing_is_clamped_to_the_wound_not_over_reported(self, table):
        """
        Healing 11 on a target missing 2 HP restores 2. Reporting 11 would make a
        ledger that lies pass a naive test.
        """
        resolver, wrapper, _ = table
        _wound(wrapper, "Target", 2)
        result = _cast(resolver, wrapper, "Cleric", spell_name="Cure Wounds")
        assert result["healing"] == 2
        assert _hp(wrapper, "Target") == 200

    def test_upcast_healing_reads_the_higher_row(self):
        srd = get_srd_rules()
        low = compile_spell(srd.spell("Cure Wounds"), slot_level=1)
        high = compile_spell(srd.spell("Cure Wounds"), slot_level=4)
        assert low.automation[0]["effects"][0]["heal"] == "1d8 + {mod}"
        assert high.automation[0]["effects"][0]["heal"] == "4d8 + {mod}"


class TestAutomaticSpells:
    """Magic Missile has neither a save nor an attack roll: it just hits."""

    def test_magic_missile_always_deals_damage(self, table):
        resolver, wrapper, manager = table
        for _ in range(5):
            manager.characters["Wiz"].spell_slots[1]["current"] = 4
            before = _hp(wrapper, "Target")
            result = _cast(resolver, wrapper, "Wiz",
                           spell_name="Magic Missile")
            assert result["success"] is True, result
            # 3d4+3 at 1st level
            assert 6 <= result["damage"] <= 15, result
            assert _hp(wrapper, "Target") < before


# ---------------------------------------------------------------------------
# 4. Needs adjudication — the silent-zero guard
# ---------------------------------------------------------------------------

class TestUnparseableSpellsAreAdjudicatedNotFaked:
    """
    243 of the 319 SRD spells carry their mechanics ONLY in prose. Each must say
    so and spend nothing — never report a successful cast that changed no state.

    `_meta.correction` in data/rules/stormlight/surgebinding.json is the precedent:
    hand-invented costs there were "plausible and wrong".
    """

    @pytest.mark.parametrize("spell", ["Bless", "Wish", "Hold Person",
                                       "Counterspell", "Polymorph"])
    def test_a_prose_only_spell_compiles_to_needs_adjudication(self, spell):
        compiled = compile_spell(get_srd_rules().spell(spell), caster_level=20)
        assert compiled.needs_adjudication is True
        assert compiled.automation == []
        assert compiled.reason, "an adjudication request with no reason is useless"

    def test_casting_one_reports_needs_adjudication_rather_than_zero_damage(
            self, table):
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz", target="Wiz",
                       spell_name="Bless")

        assert result["success"] is False
        assert result.get("needs_adjudication") is True
        assert result["damage"] == 0
        assert "judge" in result["description"].lower()

    def test_it_costs_no_slot_because_nothing_was_resolved(self, table):
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        _cast(resolver, wrapper, "Wiz", target="Wiz", spell_name="Bless")
        assert _slots(manager, "Wiz") == before

    def test_an_unknown_spell_name_is_refused_not_invented(self, table):
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        result = _cast(resolver, wrapper, "Wiz",
                       spell_name="Stormfather's Judgement")
        assert result["success"] is False
        assert "not in the SRD" in result["description"]
        assert _slots(manager, "Wiz") == before

    def test_a_cantrip_with_an_unknown_caster_level_is_not_guessed_at(self):
        """
        Cantrip damage is keyed on CHARACTER level. Without one, refuse — do not
        read row "1" and report a level-17 archmage's Fire Bolt as 1d10.
        """
        compiled = compile_spell(get_srd_rules().spell("Fire Bolt"),
                                 caster_level=None)
        assert compiled.needs_adjudication is True
        assert "level" in compiled.reason

    def test_the_executable_subset_is_measured_not_assumed(self):
        """
        A number, recorded, so a regression that quietly drops spells is visible.
        76 of 319 spells compile to a runnable tree; the rest are adjudicated.
        """
        import json

        spells = json.loads(
            (PROJECT_ROOT / "data" / "rules" / "srd" / "spells.json")
            .read_text(encoding="utf-8"))
        assert len(spells) == 319

        executable = [s for s in spells
                      if not compile_spell(s, caster_level=20).needs_adjudication]
        assert len(executable) >= 70, (
            f"only {len(executable)} spells compile — the compiler regressed")
        names = {s["name"] for s in executable}
        for required in ("Fireball", "Fire Bolt", "Cure Wounds", "Magic Missile",
                         "Ray of Frost", "Sacred Flame", "Guiding Bolt"):
            assert required in names, f"{required} stopped compiling"


# ---------------------------------------------------------------------------
# 5. Offerability — the bug that made 4 of 5 Surges unplayable
# ---------------------------------------------------------------------------

class TestCastSpellIsOfferable:
    """
    `cast_spell` needs a `spell_name`, and an action needing a parameter nothing
    supplies is filtered out of BOTH the player menu and the NPC AI's options.
    Registering the action without a supplier would leave casting exactly as
    unplayable as before, while every unit test above still passed.
    """

    def test_cast_spell_is_registered(self):
        assert "cast_spell" in ACTION_REGISTRY

    def test_it_needs_no_caller_supplied_parameter(self):
        assert required_caller_params("cast_spell") == []

    def test_it_is_offerable(self):
        assert is_offerable("cast_spell") is True

    def test_it_appears_in_the_offered_menu(self):
        assert "cast_spell" in offerable_actions()

    def test_every_defaulted_param_is_a_real_param(self):
        declared = set(ACTION_REGISTRY["cast_spell"].get("params") or [])
        for name in param_defaults("cast_spell"):
            assert name in declared, f"default for unknown param {name!r}"

    def test_the_default_supplier_actually_names_a_castable_spell(self, table):
        """
        `param_defaults` says `spell_name: None`, which only works because the
        service resolves None to a real spell. A None that reached the SRD lookup
        would refuse every cast — offerable and still unplayable.
        """
        resolver, _, _ = table
        assert resolver.spellcasting.default_spell("Wiz") is not None

    def test_the_default_prefers_a_cantrip_over_burning_a_slot(self, table):
        """A wizard should not spend a 3rd-level slot by default."""
        resolver, wrapper, manager = table
        before = _slots(manager, "Wiz")
        result = _cast(resolver, wrapper, "Wiz")  # no spell_name at all
        assert result["success"] is True, result
        assert result["slot_level"] == 0
        assert _slots(manager, "Wiz") == before

    def test_the_default_never_picks_a_spell_that_needs_adjudication(self, table):
        """
        Defaulting to Bless would make every unspecified cast a refusal — the
        `progression_healing` trap again, where the menu offered an action that
        was refused every round.
        """
        resolver, wrapper, manager = table
        # Strip the executable options; only prose-only spells remain plus a
        # cantrip, and the cantrip must win.
        manager.characters["Wiz"].spells_known = ["Bless", "Wish", "Fire Bolt"]
        assert resolver.spellcasting.default_spell("Wiz") == "Fire Bolt"


class TestOnlyCastersAreOfferedCastSpell:
    """
    Offerability is actor-independent, so without an actor gate a goblin would be
    told it can cast Fireball. Measured before the equivalent surge gate: 4 of 7
    entries on a plain goblin's menu were traps.
    """

    def test_a_fighter_is_told_why_it_cannot_cast(self, table):
        _, _, manager = table
        reason = unusable_reason("cast_spell", manager.characters["Grunt"])
        assert reason is not None
        assert "spellcaster" in reason

    def test_cast_spell_is_absent_from_a_non_casters_menu(self, table):
        _, _, manager = table
        assert "cast_spell" not in usable_actions(manager.characters["Grunt"])

    def test_cast_spell_is_present_on_a_wizards_menu(self, table):
        _, _, manager = table
        assert "cast_spell" in usable_actions(manager.characters["Wiz"])

    def test_a_caster_who_knows_no_spells_is_not_offered_casting(self, table):
        _, _, manager = table
        manager.characters["Wiz"].spells_known = []
        manager.characters["Wiz"].cantrips_known = []
        reason = unusable_reason("cast_spell", manager.characters["Wiz"])
        assert reason is not None and "knows no spells" in reason

    def test_a_slotless_caster_keeps_casting_if_they_know_a_cantrip(self, table):
        """Out of slots is not out of magic — cantrips are free."""
        _, _, manager = table
        character = manager.characters["Wiz"]
        for data in character.spell_slots.values():
            data["current"] = 0
        assert unusable_reason("cast_spell", character) is None

    def test_a_slotless_caster_with_no_cantrips_is_not_offered_casting(
            self, table):
        _, _, manager = table
        character = manager.characters["Wiz"]
        character.spells_known = ["Fireball"]
        for data in character.spell_slots.values():
            data["current"] = 0
        reason = unusable_reason("cast_spell", character)
        assert reason is not None and "no spell slots" in reason

    def test_a_fighter_who_tries_anyway_is_refused_cleanly(self, table):
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Grunt", target="Wiz",
                       spell_name="Fireball")
        assert result["success"] is False
        assert result["damage"] == 0


class TestCastSpellResolvesThroughTheGamePath:
    """
    Every test above already goes through `CombatActionResolver.resolve_action`,
    because the surge bugs all passed tests that called the action class directly.
    These check the resolver contract itself.
    """

    def test_resolution_reports_no_missing_parameter(self, table):
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz")
        assert result.get("refused") is not True
        assert "needs" not in str(result.get("description", "")).lower()

    def test_an_unknown_caster_does_not_crash_the_loop(self, table):
        resolver, _, _ = table
        result = resolver.resolve_action({"actor": "Nobody",
                                          "action_type": "cast_spell",
                                          "target": "Target"})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_a_successful_cast_costs_the_actor_its_action(self, table):
        """
        A wizard who casts cannot then attack. Nothing consumed the action economy
        before plan 1.x, and three enemies attacked four times a round.
        """
        resolver, wrapper, _ = table
        wrapper.entities["Wiz"].action_economy.reset_all_costs()
        cast = resolver.resolve_action({"actor": "Wiz",
                                        "action_type": "cast_spell",
                                        "target": "Target",
                                        "spell_name": "Fireball"})
        assert cast["success"] is True, cast
        follow_up = resolver.resolve_action({"actor": "Wiz",
                                             "action_type": "attack",
                                             "target": "Target"})
        assert follow_up["success"] is False

    def test_a_refused_cast_does_not_eat_the_turn(self, table):
        """
        The `progression_healing` failure mode: an action refused for a resource
        problem still burned the turn, and the actor silently lost it. A refusal
        must leave the economy intact so the player can do something else.
        """
        resolver, wrapper, manager = table
        manager.characters["Wiz"].spell_slots[3]["current"] = 0
        wrapper.entities["Wiz"].action_economy.reset_all_costs()

        refused = resolver.resolve_action({"actor": "Wiz",
                                           "action_type": "cast_spell",
                                           "target": "Target",
                                           "spell_name": "Fireball"})
        assert refused["success"] is False
        instead = resolver.resolve_action({"actor": "Wiz",
                                           "action_type": "attack",
                                           "target": "Target"})
        assert instead.get("error") is None, instead

    def test_the_combat_state_hp_is_synced_after_a_damaging_spell(self, table):
        """
        The narrator and the NPC AI read `combat_state`, not the engine entity. An
        unsynced kill leaves a corpse fighting on.
        """
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz", spell_name="Magic Missile")
        assert result["success"] is True
        mirrored = resolver.combat_state["combatant_states"]["Target"]["hp_current"]
        assert mirrored == _hp(wrapper, "Target")


# ---------------------------------------------------------------------------
# 6. Concentration
# ---------------------------------------------------------------------------

class TestConcentration:
    """
    One concentration spell at a time (PHB 203). The damage-triggered CON save is
    deliberately NOT implemented — see ConcentrationTracker's docstring — because
    a hook that fires for some damage sources and not others would make
    concentration merely LOOK enforced.
    """

    def test_a_concentration_spell_is_recorded(self, table):
        resolver, wrapper, _ = table
        result = _cast(resolver, wrapper, "Wiz", spell_name="Flaming Sphere")
        assert result["success"] is True, result
        assert result["concentration"] is True
        assert resolver.spellcasting.concentration.concentrating_on("Wiz") == \
            "Flaming Sphere"

    def test_a_new_concentration_spell_replaces_the_old_one(self, table):
        resolver, wrapper, _ = table
        _cast(resolver, wrapper, "Wiz", spell_name="Flaming Sphere")
        second = _cast(resolver, wrapper, "Wiz", spell_name="Vampiric Touch")
        assert second["success"] is True, second
        assert second["dropped_concentration"] == "Flaming Sphere"
        assert resolver.spellcasting.concentration.concentrating_on("Wiz") == \
            "Vampiric Touch"

    def test_a_non_concentration_spell_does_not_break_concentration(self, table):
        resolver, wrapper, _ = table
        _cast(resolver, wrapper, "Wiz", spell_name="Flaming Sphere")
        _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
        assert resolver.spellcasting.concentration.concentrating_on("Wiz") == \
            "Flaming Sphere"

    def test_two_casters_concentrate_independently(self, table):
        resolver, wrapper, _ = table
        _cast(resolver, wrapper, "Wiz", spell_name="Flaming Sphere")
        tracker = resolver.spellcasting.concentration
        tracker.start("Cleric", "Bless")
        assert tracker.concentrating_on("Wiz") == "Flaming Sphere"
        assert tracker.concentrating_on("Cleric") == "Bless"

    def test_stopping_clears_it(self):
        tracker = ConcentrationTracker()
        tracker.start("Wiz", "Flaming Sphere")
        assert tracker.stop("Wiz") == "Flaming Sphere"
        assert tracker.concentrating_on("Wiz") is None

    def test_concentration_survives_across_casts_in_one_encounter(self, table):
        """
        The service is held on the resolver, not rebuilt per cast: a per-call
        service would forget that the wizard is already concentrating.
        """
        resolver, wrapper, _ = table
        _cast(resolver, wrapper, "Wiz", spell_name="Flaming Sphere")
        assert resolver.spellcasting is resolver.spellcasting
        _cast(resolver, wrapper, "Wiz", spell_name="Fire Bolt")
        assert resolver.spellcasting.concentration.concentrating_on("Wiz")


# ---------------------------------------------------------------------------
# 7. The maneuver executor is not broken by the subclass
# ---------------------------------------------------------------------------

class TestReuseDidNotBreakManeuvers:
    """
    `SpellEffectExecutor` subclasses `ManeuverExecutor`. The maneuver node set must
    still be exactly what surgebinding.json uses, and the spell nodes must be
    additions rather than replacements.
    """

    def test_the_spell_nodes_are_additions(self):
        from components.combat.maneuver_executor import KNOWN_NODES
        from components.combat.spellcasting import SpellEffectExecutor

        assert SpellEffectExecutor.SPELL_NODES.isdisjoint(KNOWN_NODES)

    def test_an_unknown_node_type_still_raises(self, table):
        """
        The parent's contract: skipping an unknown node executes half a spell and
        reports success. Inheriting that behaviour is the point of reuse.
        """
        from components.combat.maneuver_executor import AutomationError
        from components.combat.spell_compiler import CompiledSpell

        resolver, _, manager = table
        service = resolver.spellcasting
        bogus = CompiledSpell(name="Bogus", level=1,
                              automation=[{"type": "summon_spren"}])
        stats = service.stats_for("Wiz")
        result = service.executor.cast(bogus, "Wiz", stats)
        assert result.success is False
        assert "summon_spren" in result.error

    def test_a_leftover_placeholder_raises_rather_than_dealing_zero(self, table):
        from components.combat.spell_compiler import CompiledSpell

        resolver, _, _ = table
        service = resolver.spellcasting
        broken = CompiledSpell(
            name="Broken", level=1,
            automation=[{"type": "damage", "damage": "1d6 + {stormlight}",
                         "damage_type": "fire"}])
        result = service.executor.cast(broken, "Wiz",
                                       service.stats_for("Wiz"))
        assert result.success is False
        assert "placeholder" in result.error
        assert result.damage_dealt == 0
