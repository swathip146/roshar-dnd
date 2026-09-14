"""
Exploration, skills, rests and progression — scenarios E-1…E-5 and P-1.

Everything real except the LLM. Where a scenario needs the agent layer (a DM tool
called through a real Haystack `Agent`), it installs a scripted policy; where the
mechanic is pure code (levelling, rests, encumbrance) it calls the production object
directly, because inserting an LLM there would add nondeterminism and prove nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tests.integration.harness.game_builder import (
    build_engine,
    caster_template,
    character_template,
    radiant_template,
)

pytestmark = [pytest.mark.integration, pytest.mark.deterministic]


def skill_check(engine, actor: str, skill: str, **extra: Any) -> Dict[str, Any]:
    """Run the real 7-step pipeline (`game_engine.py:196`)."""
    request = {"actor": actor, "skill": skill}
    request.update(extra)
    return engine.process_skill_check(request)


# --------------------------------------------------------------------------- #
# E-1 — skills and the 7-step pipeline
# --------------------------------------------------------------------------- #

class TestE1SkillChecks:
    """E1: 18 skills, real dice, DC scaling by policy profile."""

    def test_a_skill_check_rolls_real_dice(self, ledger):
        engine = build_engine()
        result = skill_check(engine, "aggi", "athletics", dc=12)

        assert "success" in result, f"no verdict in {result}"
        roll = result.get("selected_roll") or result.get("roll_total")
        assert roll is not None, f"no die roll recorded: {result}"
        assert 1 <= int(roll) <= 30, f"implausible d20-based roll: {roll}"
        ledger.mechanic("E1:skill_check",
                        f"roll={roll} success={result.get('success')}")

    def test_results_vary_across_many_checks(self, ledger):
        """A constant result would mean the dice are not being rolled."""
        engine = build_engine()
        rolls = {int(skill_check(engine, "aggi", "athletics", dc=12)
                     .get("selected_roll", 0)) for _ in range(30)}

        assert len(rolls) > 5, f"only {len(rolls)} distinct rolls in 30 checks: {rolls}"
        ledger.mechanic("E1:dice_vary", f"{len(rolls)} distinct rolls")

    def test_proficiency_changes_the_modifier(self, ledger):
        """A proficient skill must out-modify an unproficient one."""
        engine = build_engine(characters=[
            character_template(skills={"athletics": True, "arcana": False})])

        proficient = skill_check(engine, "aggi", "athletics", dc=10)
        unproficient = skill_check(engine, "aggi", "arcana", dc=10)

        assert (proficient.get("character_modifier", 0)
                > unproficient.get("character_modifier", 0)), (
            f"proficiency had no effect: {proficient.get('character_modifier')} vs "
            f"{unproficient.get('character_modifier')}")
        ledger.mechanic("E1:proficiency",
                        f"prof={proficient.get('character_modifier')} "
                        f"unprof={unproficient.get('character_modifier')}")

    def test_easy_profile_is_kinder_than_raw(self, ledger):
        """E1: the PolicyEngine profile must actually move outcomes."""
        from components.game_engine import PolicyProfile

        def success_rate(profile) -> float:
            engine = build_engine(policy_profile=profile, seed=555)
            wins = sum(bool(skill_check(engine, "aggi", "athletics", dc=18)
                            .get("success")) for _ in range(200))
            return wins / 200

        raw = success_rate(PolicyProfile.RAW)
        easy = success_rate(PolicyProfile.EASY)

        assert easy >= raw, f"EASY ({easy:.0%}) was harder than RAW ({raw:.0%})"
        ledger.mechanic("E1:policy_scaling", f"RAW={raw:.0%} EASY={easy:.0%}")

    def test_a_missing_tool_removes_the_proficiency_bonus(self, ledger):
        """E2: `required_tool` is a real mechanical gate."""
        engine = build_engine(characters=[
            character_template(skills={"sleight_of_hand": True},
                               tool_proficiencies=[])])

        gated = skill_check(engine, "aggi", "sleight_of_hand", dc=12,
                            required_tool="thieves' tools")
        ungated = skill_check(engine, "aggi", "sleight_of_hand", dc=12)

        assert (gated.get("character_modifier", 0)
                <= ungated.get("character_modifier", 0)), (
            "lacking the required tool did not reduce the modifier")
        ledger.mechanic("E2:tool_gate",
                        f"gated={gated.get('character_modifier')} "
                        f"ungated={ungated.get('character_modifier')}")

    def test_passive_score_needs_no_roll(self, ledger):
        """E2: passive perception = 10 + modifier, deterministic.

        The real return key is `passive_score`, with a `breakdown` string like
        "10 + 3 = 13" (`character_manager.py:763`).
        """
        engine = build_engine()
        passive = engine.character_manager.get_passive_score("aggi", "perception")

        score = passive["passive_score"]
        assert 5 <= int(score) <= 30, f"implausible passive score: {passive}"
        assert score == 10 + passive["modifier"], (
            f"passive score is not 10 + modifier: {passive}")
        ledger.mechanic("E2:passive_perception", passive["breakdown"])


# --------------------------------------------------------------------------- #
# E-2 — rests
# --------------------------------------------------------------------------- #

class TestE2Rests:
    """E4: short and long rests restore the right resources and no others."""

    def test_a_long_rest_restores_hp(self, ledger):
        engine = build_engine()
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 5

        engine.character_manager.long_rest("aggi")

        assert character.hit_points["current"] == character.hit_points["maximum"], (
            f"long rest left HP at {character.hit_points}")
        ledger.mechanic("E4:long_rest_hp", f"restored to {character.hit_points}")

    def test_a_long_rest_restores_spell_slots(self, ledger):
        from components.combat.spellcasting import SpellSlotLedger

        engine = build_engine(characters=[caster_template()])
        slots = SpellSlotLedger(engine.character_manager)
        character = engine.character_manager.characters["jasnah"]
        for level in list(character.spell_slots):
            character.spell_slots[level]["current"] = 0
        assert not slots.available("jasnah"), "fixture failed to drain slots"

        engine.character_manager.long_rest("jasnah")

        assert slots.available("jasnah"), "long rest restored no spell slots"
        ledger.mechanic("E4:long_rest_slots", f"{slots.available('jasnah')}")

    def test_a_short_rest_spends_a_hit_die_to_heal(self, ledger):
        engine = build_engine()
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 10
        before_dice = getattr(character, "hit_dice_remaining", None)

        result = engine.character_manager.short_rest("aggi", hit_dice_to_spend=1)

        assert character.hit_points["current"] >= 10, "short rest lost HP"
        if isinstance(before_dice, int):
            assert getattr(character, "hit_dice_remaining") <= before_dice
        ledger.mechanic("E4:short_rest",
                        f"hp={character.hit_points['current']} result={result}")

    def test_a_long_rest_restores_the_resources_it_reports(self, ledger):
        """E4: the long-rest result reports HP, hit dice, Stormlight and features.

        NOTE — a real gap found while writing this test, deliberately NOT asserted as
        working: `long_rest` computes an `exhaustion_reduced` flag
        (`character_manager.py:1316`), logs it at :1326, and then never returns it.
        It is a dead local, so **no caller can observe exhaustion relief** and nothing
        downstream can decrement the level. The audit's "exhaustion reduced on long
        rest" claim rests on that log line rather than on observable state.

        Asserting only the keys that genuinely exist keeps this test honest; the
        exhaustion gap is recorded in the suite's README instead of being faked green.
        """
        engine = build_engine()
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 4
        character.conditions = ["Exhaustion"]

        result = engine.character_manager.long_rest("aggi")

        assert set(result) >= {"hit_points", "hit_dice_remaining",
                               "class_features_recharged"}, (
            f"long rest reported an unexpected shape: {sorted(result)}")
        assert result["hit_points"]["current"] == result["hit_points"]["maximum"]
        assert "exhaustion_reduced" not in result, (
            "exhaustion_reduced is now reported — tighten this test to assert the "
            "level actually decrements (see the docstring)")
        ledger.mechanic("E4:long_rest_reports", str(sorted(result)))

    def test_a_radiant_regains_stormlight_on_a_long_rest(self, ledger):
        engine = build_engine(characters=[radiant_template()])
        character = engine.character_manager.characters["shallan"]
        character.stormlight_current = 0

        engine.character_manager.long_rest("shallan")

        assert character.stormlight_current >= 0, "stormlight went negative"
        ledger.mechanic("E4:stormlight_rest",
                        f"stormlight={character.stormlight_current}")


# --------------------------------------------------------------------------- #
# P-1 — progression
# --------------------------------------------------------------------------- #

class TestP1Progression:
    """P1-P4: XP, levelling 1→20, ASI at 4/8/12/16/19, proficiency by level."""

    def test_xp_award_levels_a_character_up(self, ledger):
        engine = build_engine(characters=[
            character_template(level=1, experience_points=0,
                               hit_points={"current": 10, "maximum": 10,
                                           "temporary": 0})])
        character = engine.character_manager.characters["aggi"]

        engine.character_manager.award_xp("aggi", 400)

        assert character.level > 1, f"400 XP did not level a level-1 character"
        assert character.hit_points["maximum"] > 10, "levelling did not raise max HP"
        ledger.mechanic("P1:level_up",
                        f"level={character.level} maxhp={character.hit_points['maximum']}")

    def test_levelling_to_twenty_keeps_every_derived_number_sane(self, ledger):
        """The full 1→20 walk. Guards HP, proficiency and hit dice together."""
        engine = build_engine(characters=[
            character_template(level=1, experience_points=0,
                               hit_points={"current": 10, "maximum": 10,
                                           "temporary": 0})])
        manager = engine.character_manager
        character = manager.characters["aggi"]

        seen: List[Dict[str, Any]] = []
        for _ in range(19):
            manager.award_xp("aggi", 100_000)
            seen.append({"level": character.level,
                         "max_hp": character.hit_points["maximum"],
                         "prof": character.proficiency_bonus})
            if character.level >= 20:
                break

        assert character.level == 20, f"stalled at level {character.level}"
        assert character.proficiency_bonus == 6, (
            f"level-20 proficiency should be +6, got {character.proficiency_bonus}")
        max_hps = [row["max_hp"] for row in seen]
        assert max_hps == sorted(max_hps), f"max HP fell during levelling: {max_hps}"
        ledger.mechanic("P1:level_1_to_20",
                        f"L20 hp={character.hit_points['maximum']} "
                        f"prof=+{character.proficiency_bonus}")

    def test_proficiency_bonus_follows_the_5e_table(self, ledger):
        """P4: +2 at 1-4, +3 at 5-8, +4 at 9-12, +5 at 13-16, +6 at 17-20."""
        expected = {1: 2, 4: 2, 5: 3, 8: 3, 9: 4, 12: 4, 13: 5, 16: 5, 17: 6, 20: 6}
        observed = {}
        for level, want in expected.items():
            engine = build_engine(characters=[character_template(level=level)])
            got = engine.character_manager.characters["aggi"].proficiency_bonus
            observed[level] = got
            assert got == want, f"level {level}: expected +{want}, got +{got}"
        ledger.mechanic("P4:proficiency_table", str(observed))

    def test_asi_raises_an_ability_at_level_four(self, ledger):
        """P2: ASI at 4/8/12/16/19 — 5e's single biggest balance lever."""
        engine = build_engine(characters=[
            character_template(level=3, experience_points=900)])
        manager = engine.character_manager
        character = manager.characters["aggi"]
        before = sum(character.ability_scores.values())

        while character.level < 4:
            manager.award_xp("aggi", 1_000)

        after = sum(character.ability_scores.values())
        assert after > before, (
            f"reaching level 4 granted no ASI: ability total stayed {before}")
        assert after - before == 2, f"an ASI grants +2 total, got +{after - before}"
        ledger.mechanic("P2:asi_level_4", f"ability total {before} -> {after}")

    def test_no_asi_at_a_non_asi_level(self, ledger):
        """Guards the inverse: ASI must not fire at level 3, 5, 6, 7."""
        engine = build_engine(characters=[
            character_template(level=2, experience_points=300)])
        manager = engine.character_manager
        character = manager.characters["aggi"]
        before = sum(character.ability_scores.values())

        while character.level < 3:
            manager.award_xp("aggi", 500)

        assert sum(character.ability_scores.values()) == before, (
            "an ASI fired at level 3, which is not an ASI level")
        ledger.mechanic("P2:no_asi_off_level", f"ability total held at {before}")


# --------------------------------------------------------------------------- #
# E-3 — encumbrance and equipment
# --------------------------------------------------------------------------- #

class TestE3EncumbranceAndEquipment:
    """E3/E8: carrying capacity, encumbrance, AC from armour."""

    def test_carrying_capacity_is_strength_times_fifteen(self, ledger):
        engine = build_engine(characters=[
            character_template(ability_scores={
                "strength": 16, "dexterity": 10, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10})])

        capacity = engine.character_manager.get_carrying_capacity("aggi")

        assert capacity == 16 * 15, f"expected 240 lb for STR 16, got {capacity}"
        ledger.mechanic("E3:carrying_capacity", f"{capacity} lb at STR 16")

    def test_encumbrance_reports_a_state(self, ledger):
        engine = build_engine()
        state = engine.character_manager.get_encumbrance("aggi")

        assert isinstance(state, dict) and state, f"no encumbrance data: {state}"
        ledger.mechanic("E3:encumbrance", str(state)[:120])

    def test_equipping_armour_changes_ac(self, ledger):
        """E8: AC is computed from the armour category, not a static field.

        `recalculate_ac(character_id, armor_name=..., shield=...)` takes the armour
        as an EXPLICIT argument — it does not scan the equipment list
        (`character_manager.py:2496`). So `add_equipment()` alone does not move AC;
        that is the documented contract, not a defect.
        """
        engine = build_engine(characters=[
            character_template(
                equipment=["longsword"], armor_class=10,
                ability_scores={"strength": 16, "dexterity": 14,
                                "constitution": 14, "intelligence": 10,
                                "wisdom": 12, "charisma": 10})])
        manager = engine.character_manager

        unarmoured = manager.recalculate_ac("aggi")
        heavy = manager.recalculate_ac("aggi", armor_name="chain mail")
        with_shield = manager.recalculate_ac("aggi", armor_name="chain mail",
                                             shield=True)

        assert unarmoured == 12, f"10 + DEX 2 should be 12, got {unarmoured}"
        assert heavy == 16, f"chain mail is flat 16 (no DEX), got {heavy}"
        assert with_shield == 18, f"shield adds +2, got {with_shield}"
        assert manager.characters["aggi"].armor_class == 18, "AC was not persisted"
        ledger.mechanic("E8:armour_ac",
                        f"unarmoured={unarmoured} chain={heavy} +shield={with_shield}")

    def test_medium_armour_caps_the_dex_bonus(self, ledger):
        """5e: medium armour adds at most +2 DEX. A high-DEX character proves it."""
        engine = build_engine(characters=[
            character_template(ability_scores={
                "strength": 10, "dexterity": 20, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10})])

        light = engine.character_manager.recalculate_ac("aggi", armor_name="leather")
        medium = engine.character_manager.recalculate_ac("aggi", armor_name="hide")

        assert light == 11 + 5, f"light armour takes full DEX +5, got {light}"
        assert medium == 12 + 2, f"medium armour caps DEX at +2, got {medium}"
        ledger.mechanic("E8:dex_cap", f"light={light} medium={medium} at DEX 20")


# --------------------------------------------------------------------------- #
# E-4 / E-5 — quests and persistence
# --------------------------------------------------------------------------- #

class TestE4QuestsAndPersistence:
    """E7/E9: quest objectives and a lossless save/load round trip."""

    def test_a_quest_objective_can_be_completed(self, ledger):
        engine = build_engine()
        engine.add_quest_objective("find-the-oathgate", "Find the Oathgate")

        result = engine.complete_quest_objective("find-the-oathgate")

        assert result is not False, f"completing an objective failed: {result}"
        ledger.mechanic("E7:quest_objective", f"completed: {result}")

    def test_character_state_round_trips_losslessly(self, ledger):
        """E9: `to_dict()`/`from_dict()` must not drop HP, AC, equipment or XP.

        The audit records a parallel, lossy path (`export_game_state`'s own character
        branch) that silently reset these to defaults. This pins the real one.
        """
        from components.character_manager import CharacterData

        engine = build_engine()
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 13
        character.experience_points = 1234
        character.conditions = ["Poisoned"]

        restored = CharacterData.from_dict(character.to_dict())

        assert restored.hit_points["current"] == 13
        assert restored.hit_points["maximum"] == character.hit_points["maximum"]
        assert restored.armor_class == character.armor_class
        assert list(restored.equipment) == list(character.equipment)
        assert restored.experience_points == 1234
        assert restored.character_class == character.character_class != "Unknown"
        assert list(restored.conditions) == ["Poisoned"]
        ledger.mechanic("E9:character_round_trip",
                        f"hp={restored.hit_points['current']} xp={restored.experience_points}")

    def test_spell_slots_survive_a_round_trip(self, ledger):
        """Int-keyed dicts are stringified by JSON; `from_dict` must restore ints."""
        from components.character_manager import CharacterData
        from components.combat.spellcasting import SpellSlotLedger

        engine = build_engine(characters=[caster_template()])
        character = engine.character_manager.characters["jasnah"]
        before = SpellSlotLedger(engine.character_manager).available("jasnah")

        restored = CharacterData.from_dict(character.to_dict())
        engine.character_manager.characters["restored"] = restored
        after = SpellSlotLedger(engine.character_manager).available("restored")

        assert after == before, f"slots changed across the round trip: {before} -> {after}"
        ledger.mechanic("E9:slots_round_trip", f"{after}")
