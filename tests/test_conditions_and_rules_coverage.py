"""
The two PHB conditions the vendored engine never implemented, and the rules long tail.

TWO GAPS, FOUND THE SAME WAY: by differencing what is DATA against what is REACHABLE.

  conditions   `data/rules/srd/conditions.json` lists 15. `dnd.conditions` implements
               13. Missing: **Petrified and Exhaustion**. (The plan said one — it
               named Petrified and missed Exhaustion.)

  rules 2.10   `SRDRules` loaded ten datasets (1,321 entries) from the start, but
               `query_rules` searched only four — monsters, spells, conditions,
               equipment. So 386 entries across six datasets were loaded and
               unreachable, and a lookup for "Perception" — plainly in skills.json —
               fell through to the rules judge. `data/rules/gaps.json` recorded it
               happening: `"rules lookup perception"`, tier `judged`.

The second is the project's recurring failure mode, in miniature: the data was fine,
the component was fine, and nothing connected them. A test that called `srd.skill()`
directly would have passed while the game still improvised the answer. So the tests
below go through `query_rules` — the seam the model actually calls — not through
`SRDRules` alone.

Assertions are on OUTCOMES wherever an outcome exists: Petrified halves damage taken
(5 of 10) rather than merely owning a resistance modifier, and exhaustion's attack
disadvantage is measured as a drop in hit rate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.engine_conditions import MAX_EXHAUSTION_LEVEL
from components.srd_rules import SRDRules, get_srd_rules

# Every ability the level-3 clause must reach.
ABILITIES = ("strength", "dexterity", "constitution",
             "intelligence", "wisdom", "charisma")


class _Engine:
    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, **over):
    base = {
        "character_id": char_id, "name": char_id, "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 14, "constitution": 12,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        # Deliberately huge, so damage tests never accidentally drop to 0 HP and
        # start triggering death saves instead of measuring resistance.
        "hit_points": {"current": 5000, "maximum": 5000, "temporary": 0},
        "armor_class": 13, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 2,
    }
    base.update(over)
    return base


@pytest.fixture
def arena():
    """Two adjacent combatants. Adjacent so melee range is never the confound."""
    from components.combat.battle_map import parse_map
    from components.combat.tactical_grid import TacticalGrid

    TacticalGrid._clear_tiles()
    manager = CharacterManager()
    for char_id in ("hero", "orc"):
        manager.add_character(_sheet(char_id))

    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                               character_manager=manager)
    grid = TacticalGrid(parse_map({"rows": ["P.....", "......",
                                           "......", ".....E"]}), wrapper)
    grid.build_terrain()
    wrapper.set_entity_position("hero", (0, 0))
    wrapper.set_entity_position("orc", (1, 0))
    wrapper.refresh_senses()
    yield wrapper
    grid.teardown()
    TacticalGrid._clear_tiles()


def _hit_rate(wrapper, attacker, target, trials=400):
    """
    Fraction of attacks that land.

    CRIT counts as a hit. Substring-matching "HIT" excludes AttackOutcome.CRIT,
    which makes a paralyzed target measure as 0% — unhittable rather than auto-crit.
    """
    from dnd.actions import Attack
    from dnd.blocks.equipment import WeaponSlot

    entity = wrapper.entities[attacker]
    hits = 0
    for _ in range(trials):
        entity.action_economy.reset_all_costs()
        event = Attack(source_entity_uuid=entity.uuid,
                       target_entity_uuid=wrapper.entities[target].uuid,
                       weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        outcome = str(getattr(event, "attack_outcome", ""))
        if outcome.rsplit(".", 1)[-1] in ("HIT", "CRIT"):
            hits += 1
    return hits / trials


def _exhaust(wrapper, char_id, level):
    import dnd.conditions as conditions

    entity = wrapper.entities[char_id]
    entity.add_condition(conditions.Exhaustion(
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
        level=level))
    return entity


# ---------------------------------------------------------------------------
# The gap itself
# ---------------------------------------------------------------------------

class TestTheConditionGapIsClosed:
    """Every condition the SRD defines is now implemented."""

    def test_srd_defines_fifteen_conditions(self):
        import json

        data = json.loads(
            (PROJECT_ROOT / "data" / "rules" / "srd"
             / "conditions.json").read_text())
        assert len(data) == 15

    def test_every_srd_condition_is_implemented(self):
        """
        The check that found the gap. Compare the two SETS rather than trusting
        either the engine's docs or the plan's prose — the plan named Petrified and
        missed Exhaustion.
        """
        import json

        import components.dnd_engine_wrapper  # noqa: F401  (applies the patches)
        import dnd.conditions as conditions

        srd_names = {c["name"] for c in json.loads(
            (PROJECT_ROOT / "data" / "rules" / "srd"
             / "conditions.json").read_text())}
        missing = {n for n in srd_names if getattr(conditions, n, None) is None}
        assert not missing, f"conditions in the SRD but not implemented: {missing}"

    @pytest.mark.parametrize("name", ["Petrified", "Exhaustion"])
    def test_the_two_added_conditions_exist(self, name):
        import components.dnd_engine_wrapper  # noqa: F401
        import dnd.conditions as conditions

        assert getattr(conditions, name, None) is not None

    def test_registration_is_idempotent(self):
        """
        Re-registering must not rebind the classes: an instance already applied to
        an entity would be left pointing at an orphaned class.
        """
        import dnd.conditions as conditions
        from components.engine_conditions import register_missing_conditions

        before = conditions.Petrified
        register_missing_conditions()
        assert conditions.Petrified is before

    @pytest.mark.parametrize("spelling", ["petrified", "Petrified", "PETRIFIED",
                                          "stone", "exhaustion", "exhausted"])
    def test_wrapper_resolves_both_by_name(self, arena, spelling):
        """
        Reachable through the WRAPPER, not just importable. Registering the class
        without adding the alias would leave `apply_condition` returning False.
        """
        assert arena.apply_condition("hero", spelling) is True


class TestConditionsThatShareASubConditionCanStack:
    """
    A SEPARATE UPSTREAM BUG, found while testing the two new conditions.

        Stunned, then Unconscious  ->  True, False
        "list.remove(x): x not in list"

    Five of the fifteen conditions apply `Incapacitated` as a sub-condition.
    `Entity.add_condition` refuses a duplicate by NAME, so the second one is
    rejected — but it already carries `parent_condition`, and the rejection path
    calls `parent.sub_conditions.remove(uuid)` for a uuid never appended. The
    ValueError escapes and the whole outer condition fails to apply.

    Nothing to do with Petrified: it reproduces with two engine-native conditions.
    A per-condition test could never catch it, because it needs TWO on one entity —
    `Unconscious` alone always worked. Fixed in `components/engine_patches.py`.
    """

    @pytest.mark.parametrize("first,second", [
        ("Stunned", "Unconscious"),
        ("Paralyzed", "Unconscious"),
        ("Petrified", "Unconscious"),
        ("Unconscious", "Stunned"),
        ("Petrified", "Stunned"),
        ("Incapacitated", "Unconscious"),
    ])
    def test_two_conditions_sharing_incapacitated_both_apply(self, arena,
                                                             first, second):
        assert arena.apply_condition("hero", first) is True, first
        assert arena.apply_condition("hero", second) is True, (
            f"{second} failed to apply on top of {first}")

    def test_every_srd_condition_applies_on_one_entity(self, arena):
        """
        All fifteen onto a single entity in sequence. This is the check that
        surfaced the bug: each condition passed alone, and `Unconscious` failed
        only once something else had already applied `Incapacitated`.
        """
        import json

        srd_path = (PROJECT_ROOT / "data" / "rules" / "srd" / "conditions.json")
        failures = [entry["name"]
                    for entry in json.loads(srd_path.read_text())
                    if not arena.apply_condition("hero", entry["name"])]
        assert not failures, f"could not apply while others were active: {failures}"

    def test_removing_the_outer_condition_leaves_the_other_intact(self, arena):
        """
        The shared `Incapacitated` belongs to whichever condition applied it first.
        Removing the second must not tear down the first one's sub-condition.
        """
        arena.apply_condition("hero", "Stunned")
        arena.apply_condition("hero", "Unconscious")
        assert arena.remove_condition("hero", "Unconscious") is True

        remaining = arena.get_conditions("hero")
        assert "Stunned" in remaining
        assert "Unconscious" not in remaining


# ---------------------------------------------------------------------------
# Petrified
# ---------------------------------------------------------------------------

class TestPetrified:
    """
    PHB: incapacitated, can't move or speak; attacks against it have advantage;
    auto-fails STR and DEX saves; resistance to ALL damage; immune to poison.
    """

    def test_resistance_halves_damage_actually_taken(self, arena):
        """
        The clause that makes Petrified survivable rather than a death sentence.
        Asserted on damage TAKEN, not on the presence of a modifier.
        """
        from dnd.core.modifiers import DamageType

        entity = arena.entities["hero"]
        assert entity.health.take_damage(10, DamageType.SLASHING,
                                         entity.uuid) == 10

        arena.apply_condition("hero", "petrified")
        assert entity.health.take_damage(10, DamageType.SLASHING,
                                         entity.uuid) == 5

    def test_resistance_covers_every_damage_type(self, arena):
        """
        The engine keys resistance per type with no wildcard, so "all damage" has
        to be enumerated. A missing type would be a silent hole.
        """
        from dnd.core.modifiers import DamageType

        arena.apply_condition("hero", "petrified")
        health = arena.entities["hero"].health
        for damage_type in DamageType:
            assert health.damage_multiplier(damage_type) <= 0.5, damage_type

    def test_poison_is_immunity_not_resistance(self, arena):
        """
        The PHB lists poison immunity separately from the damage resistance. A
        stone statue takes NO poison damage, not half.
        """
        from dnd.core.modifiers import DamageType

        arena.apply_condition("hero", "petrified")
        entity = arena.entities["hero"]
        assert entity.health.damage_multiplier(DamageType.POISON) == 0
        assert entity.health.take_damage(10, DamageType.POISON, entity.uuid) == 0

    def test_incapacitated_and_speed_zero(self, arena):
        """Delegated to the engine's own Incapacitated rather than reimplemented."""
        entity = arena.entities["hero"]
        assert entity.action_economy.movement.score > 0

        arena.apply_condition("hero", "petrified")
        assert entity.action_economy.movement.score == 0
        assert "Incapacitated" in arena.get_conditions("hero")

    def test_attacks_against_it_have_advantage(self, arena):
        """Measured as a rise in hit rate, not as a modifier lookup."""
        base = _hit_rate(arena, "orc", "hero", 400)
        arena.apply_condition("hero", "petrified")
        petrified = _hit_rate(arena, "orc", "hero", 400)
        assert petrified > base + 0.10, f"{base:.3f} -> {petrified:.3f}"

    @pytest.mark.parametrize("ability", ["strength", "dexterity"])
    def test_auto_fails_strength_and_dexterity_saves(self, arena, ability):
        from dnd.core.modifiers import AutoHitStatus

        arena.apply_condition("hero", "petrified")
        save = arena.entities["hero"].saving_throws.get_saving_throw(ability)
        assert save.bonus.auto_hit == AutoHitStatus.AUTOMISS

    @pytest.mark.parametrize("ability", ["constitution", "wisdom", "charisma"])
    def test_other_saves_are_untouched(self, arena, ability):
        """RAW names STR and DEX only. Blanketing all six would be wrong."""
        from dnd.core.modifiers import AutoHitStatus

        arena.apply_condition("hero", "petrified")
        save = arena.entities["hero"].saving_throws.get_saving_throw(ability)
        assert save.bonus.auto_hit != AutoHitStatus.AUTOMISS

    def test_does_not_grant_auto_crit_like_paralyzed(self, arena):
        """
        Petrified is built from Paralyzed's structure, and Paralyzed grants an
        auto-crit within 5 ft. Copying it wholesale would make every hit on a
        statue a critical. RAW gives Petrified advantage only.
        """
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        arena.apply_condition("hero", "petrified")
        orc = arena.entities["orc"]
        outcomes = set()
        for _ in range(120):
            orc.action_economy.reset_all_costs()
            event = Attack(source_entity_uuid=orc.uuid,
                           target_entity_uuid=arena.entities["hero"].uuid,
                           weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
            outcomes.add(str(getattr(event, "attack_outcome", "")).rsplit(".", 1)[-1])
        assert "MISS" in outcomes, "a petrified target should still be missable"

    def test_removal_restores_everything(self, arena):
        """
        Conditions live on the entity, which outlives the encounter. A modifier
        applied but not returned for removal is a permanent one.
        """
        from dnd.core.modifiers import DamageType

        entity = arena.entities["hero"]
        arena.apply_condition("hero", "petrified")
        arena.remove_condition("hero", "petrified")

        assert entity.health.damage_multiplier(DamageType.SLASHING) == 1
        assert entity.health.damage_multiplier(DamageType.POISON) == 1
        assert entity.action_economy.movement.score > 0
        assert entity.health.take_damage(10, DamageType.SLASHING,
                                         entity.uuid) == 10


# ---------------------------------------------------------------------------
# Exhaustion
# ---------------------------------------------------------------------------

class TestExhaustion:
    """
    PHB p.291, six CUMULATIVE levels:
        1 disadvantage on ability checks   4 hit point maximum halved
        2 speed halved                     5 speed reduced to 0
        3 disadvantage on attacks/saves    6 death
    """

    def test_level_one_gives_checks_disadvantage(self, arena):
        from dnd.core.modifiers import AdvantageStatus

        entity = arena.entities["hero"]
        skill = entity.skill_set.get_skill("athletics")
        assert skill.skill_bonus.advantage == AdvantageStatus.NONE

        _exhaust(arena, "hero", 1)
        assert (entity.skill_set.get_skill("athletics").skill_bonus.advantage
                == AdvantageStatus.DISADVANTAGE)

    @pytest.mark.parametrize("level", [1, 2])
    def test_levels_one_and_two_do_NOT_touch_attacks(self, arena, level):
        """
        THE BUG THIS CAUGHT. Disadvantage on ability checks was first applied to
        `ability_scores.<x>.ability_score` — which reads like "the ability", but
        attack rolls derive from the same value. Level 1 therefore gave attack
        disadvantage too: measured 0.63 -> 0.35, when RAW does not touch attacks
        until level 3. The per-skill `skill_bonus` is the correct seam.
        """
        from dnd.core.modifiers import AdvantageStatus

        base = _hit_rate(arena, "hero", "orc", 400)
        entity = _exhaust(arena, "hero", level)

        assert entity.equipment.attack_bonus.advantage == AdvantageStatus.NONE
        after = _hit_rate(arena, "hero", "orc", 400)
        assert abs(after - base) < 0.10, (
            f"level {level} changed the hit rate {base:.3f} -> {after:.3f}; "
            f"RAW gives attack disadvantage only from level 3")

    def test_level_two_halves_speed(self, arena):
        entity = arena.entities["hero"]
        speed = entity.action_economy.movement.score
        _exhaust(arena, "hero", 2)
        assert entity.action_economy.movement.score == speed // 2

    def test_level_three_gives_attack_disadvantage(self, arena):
        base = _hit_rate(arena, "hero", "orc", 400)
        _exhaust(arena, "hero", 3)
        after = _hit_rate(arena, "hero", "orc", 400)
        # Disadvantage is worth about -20pp; require a clear drop, not the exact figure.
        assert after < base - 0.10, f"{base:.3f} -> {after:.3f}"

    @pytest.mark.parametrize("ability", ABILITIES)
    def test_level_three_gives_save_disadvantage_on_all_six(self, arena, ability):
        from dnd.core.modifiers import AdvantageStatus

        _exhaust(arena, "hero", 3)
        save = arena.entities["hero"].saving_throws.get_saving_throw(ability)
        assert save.bonus.advantage == AdvantageStatus.DISADVANTAGE

    def test_level_four_halves_hit_point_maximum(self, arena):
        """
        Max HP must come from `get_entity_max_hp`. `get_max_hit_dices_points()`
        ignores `max_hit_points_bonus` — the very value this clause writes.
        """
        entity = arena.entities["hero"]
        before = DnDEngineWrapper.get_entity_max_hp(entity)
        _exhaust(arena, "hero", 4)
        assert DnDEngineWrapper.get_entity_max_hp(entity) == before - before // 2

    def test_level_five_reduces_speed_to_zero(self, arena):
        entity = arena.entities["hero"]
        _exhaust(arena, "hero", 5)
        assert entity.action_economy.movement.score == 0

    def test_levels_are_cumulative(self, arena):
        """
        "A creature suffers the effect of its current level as well as all lower
        levels." Level 5 must still carry level 4's halved HP maximum.
        """
        from dnd.core.modifiers import AdvantageStatus

        entity = arena.entities["hero"]
        before = DnDEngineWrapper.get_entity_max_hp(entity)
        _exhaust(arena, "hero", 5)

        assert entity.action_economy.movement.score == 0                   # 5
        assert DnDEngineWrapper.get_entity_max_hp(entity) < before         # 4
        assert (entity.equipment.attack_bonus.advantage
                == AdvantageStatus.DISADVANTAGE)                           # 3
        assert (entity.skill_set.get_skill("athletics").skill_bonus.advantage
                == AdvantageStatus.DISADVANTAGE)                           # 1

    def test_level_six_is_reported(self, arena, caplog):
        """
        Level 6 is death. It is RECORDED, not enacted: killing the entity is the
        session's call, since it owns death saves and the endgame. Silently
        removing a character mid-resolution would be worse than surfacing it.
        """
        import logging

        with caplog.at_level(logging.WARNING):
            _exhaust(arena, "hero", MAX_EXHAUSTION_LEVEL)
        assert any("exhaustion level 6" in r.message.lower()
                   for r in caplog.records)

    def test_out_of_range_levels_are_clamped(self, arena):
        """A level of 99 or 0 must not produce a nonsensical entity."""
        entity = _exhaust(arena, "hero", 99)
        assert entity.action_economy.movement.score == 0

    def test_removal_restores_everything(self, arena):
        from dnd.core.modifiers import AdvantageStatus

        entity = arena.entities["hero"]
        speed = entity.action_economy.movement.score
        max_hp = DnDEngineWrapper.get_entity_max_hp(entity)

        _exhaust(arena, "hero", 5)
        entity.remove_condition("Exhaustion")

        assert entity.action_economy.movement.score == speed
        assert DnDEngineWrapper.get_entity_max_hp(entity) == max_hp
        assert (entity.skill_set.get_skill("athletics").skill_bonus.advantage
                == AdvantageStatus.NONE)
        assert entity.equipment.attack_bonus.advantage == AdvantageStatus.NONE


# ---------------------------------------------------------------------------
# The rules long tail (2.10)
# ---------------------------------------------------------------------------

class TestEveryLoadedDatasetIsReachable:
    """
    `SRDRules` loaded ten datasets; `query_rules` searched four. 386 entries were
    loaded and unreachable.
    """

    def test_all_ten_datasets_load(self):
        available = get_srd_rules().available()
        assert set(available) == set(SRDRules.DATASETS), (
            f"missing: {set(SRDRules.DATASETS) - set(available)}")
        assert sum(available.values()) > 1300

    def test_lookup_order_covers_every_dataset(self):
        """
        A dataset absent from LOOKUP_ORDER is loaded but unsearchable — exactly the
        bug this closes, so guard against it reappearing.
        """
        covered = {dataset for _, dataset in SRDRules.LOOKUP_ORDER}
        assert covered == set(SRDRules.DATASETS), (
            f"loaded but not searchable: {set(SRDRules.DATASETS) - covered}")

    @pytest.mark.parametrize("topic,kind", [
        ("Goblin", "monster"),               # the four that already worked
        ("Fireball", "spell"),
        ("Prone", "condition"),
        ("Longsword", "equipment"),
        ("Perception", "skill"),             # the six that did not
        ("Stealth", "skill"),
        ("Bag of Holding", "magic_item"),
        ("Finesse", "weapon_property"),
        ("Necrotic", "damage_type"),
        ("Dexterity", "ability_score"),
        ("Combat", "rule"),
    ])
    def test_lookup_resolves_to_the_right_dataset(self, topic, kind):
        hit = get_srd_rules().lookup(topic)
        assert hit is not None, f"{topic!r} is in the SRD but was not found"
        assert hit["kind"] == kind, f"{topic!r} -> {hit['kind']}, expected {kind}"

    def test_exact_match_beats_a_fuzzy_match_in_an_earlier_dataset(self):
        """
        THE BUG THIS CAUGHT. magic_items is searched before damage_types, and its
        FUZZY match won: "Necrotic" resolved to "Potion of Necrotic Resistance".
        No priority ordering fixes that — exactness has to outrank position, so
        `lookup` makes two passes.
        """
        hit = get_srd_rules().lookup("Necrotic")
        assert hit["data"]["name"] == "Necrotic"

    def test_ability_scores_are_found_by_full_name(self):
        """
        ability_scores.json keys entries "STR"/"DEX" and puts the searchable word in
        `full_name`, which `_find` never consulted — so "Dexterity" found nothing.
        """
        srd = get_srd_rules()
        assert srd.lookup("Dexterity") is not None
        assert srd.lookup("DEX") is not None

    def test_fuzzy_matching_still_works(self):
        """The two-pass change must not cost us partial matches."""
        hit = get_srd_rules().lookup("goblin warrior")
        assert hit["data"]["name"] == "Goblin"

    def test_unknown_topics_still_return_nothing(self):
        """
        Widening the search must not make it credulous. Cosmere terms have to keep
        falling through to Tier 2 / the judge.
        """
        srd = get_srd_rules()
        for topic in ("Voidbringer", "Lightweaving", "First Ideal", "Fused"):
            assert srd.lookup(topic) is None, f"{topic} should not match the SRD"

    @pytest.mark.parametrize("kind", ["monster", "spell", "condition", "skill",
                                      "equipment", "magic_item",
                                      "weapon_property", "damage_type",
                                      "ability_score", "rule"])
    def test_an_explicit_kind_restricts_the_search(self, kind):
        """Asking for a monster named "Fireball" should not return the spell."""
        hit = get_srd_rules().lookup("Fireball", kind=kind)
        if hit is not None:
            assert hit["kind"] == kind


class TestQueryRulesReachesTheWiderSurface:
    """
    Through `query_rules` — the tool the model actually calls. Testing `SRDRules`
    alone would pass while the game still improvised the answer; that is precisely
    how this gap survived.
    """

    @pytest.fixture(autouse=True)
    def _context(self):
        from agents.dm_tools import clear_dm_tool_context, set_dm_tool_context

        clear_dm_tool_context()
        set_dm_tool_context(srd_rules=get_srd_rules())
        yield
        clear_dm_tool_context()

    def _query(self, topic, **kwargs):
        import agents.dm_tools as dm_tools

        # `@tool` wraps the function; unwrap it and call it directly, the same way
        # tests/test_rules_judge_wiring.py does.
        query_rules = getattr(dm_tools.query_rules, "function",
                              dm_tools.query_rules)
        return query_rules(topic=topic, **kwargs)

    @pytest.mark.parametrize("topic", ["Perception", "Stealth", "Bag of Holding",
                                       "Finesse", "Necrotic", "Dexterity",
                                       "Combat"])
    def test_previously_unreachable_topics_now_answer_at_tier_one(self, topic):
        """
        Each of these was loaded in the SRD yet fell through to the rules judge.
        `data/rules/gaps.json` shows "rules lookup perception" recorded as `judged`.
        """
        result = self._query(topic)
        assert result.get("found") is True, f"{topic!r} still not found"
        assert result.get("tier") == 1, f"{topic!r} answered at tier {result.get('tier')}"
        assert "SRD" in result.get("source", "")

    @pytest.mark.parametrize("topic", ["Goblin", "Fireball", "Prone", "Longsword"])
    def test_the_four_that_already_worked_still_work(self, topic):
        result = self._query(topic)
        assert result.get("found") is True and result.get("tier") == 1

    @pytest.mark.parametrize("name", ["Petrified", "Exhaustion"])
    def test_the_two_new_conditions_are_queryable(self, name):
        """
        The rules text has to be reachable too, not just the mechanical effect —
        the DM needs to be able to quote what the condition does.
        """
        result = self._query(name)
        assert result.get("found") is True
        assert result.get("kind") == "condition"

    def test_a_genuine_gap_is_still_reported_honestly(self):
        """
        Widening Tier 1 must not turn "no rule" into a false positive. With no judge
        configured, an unknown topic must come back not-found and say so.
        """
        result = self._query("Voidbringer")
        assert result.get("found") is False
        assert "improvise" in result.get("note", "").lower()

    def test_an_unknown_topic_is_recorded_as_a_gap(self):
        """The tracker is what ranks the 2.11 backlog; it must still fire."""
        from agents.dm_tools import set_dm_tool_context

        recorded = []
        tracker = type("T", (), {
            "record": lambda self, situation, tier: recorded.append((situation, tier))
        })()
        set_dm_tool_context(srd_rules=get_srd_rules(), gap_tracker=tracker)

        self._query("Voidbringer")
        assert recorded and "voidbringer" in recorded[0][0].lower()

    def test_a_found_rule_is_NOT_recorded_as_a_gap(self):
        """
        The inverse, and the one that proves the fix landed: "Perception" used to be
        logged as a gap on every lookup. It must not be any more.
        """
        from agents.dm_tools import set_dm_tool_context

        recorded = []
        tracker = type("T", (), {
            "record": lambda self, situation, tier: recorded.append((situation, tier))
        })()
        set_dm_tool_context(srd_rules=get_srd_rules(), gap_tracker=tracker)

        self._query("Perception")
        assert not recorded, f"a Tier-1 hit was still logged as a gap: {recorded}"
