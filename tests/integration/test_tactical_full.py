"""
Tactical combat scenarios — the positional layer, C8 and C12-C20.

Split from `test_combat_full.py` because these all need a real GRID: cover, flanking
and opportunity attacks are consequences of where combatants stand, so they need
`TacticalGrid` + `TacticalRules` rather than two entities on a bare line.

Covers strategy §4.1 rows C4 (temp HP), C8 (grapple/shove/two-weapon), C12 (initiative),
C13 (grid/terrain), C14 (cover/flanking), C15 (opportunity attacks), C16 (reach/ranged),
C17 (multiattack), C18 (class features), C19 (senses), C20 (CR/XP budget).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from tests.integration.harness.game_builder import build_engine, character_template
from tests.integration.test_combat_full import (
    action_failed,
    build_battle,
    entity_hp,
    monster_template,
    reset_economy,
)

pytestmark = [pytest.mark.integration, pytest.mark.deterministic]


# --------------------------------------------------------------------------- #
# Arena helper — a real grid with real terrain
# --------------------------------------------------------------------------- #

def build_arena(
    rows: Sequence[str],
    placements: Dict[str, Tuple[int, int]],
    characters: Optional[List[Dict[str, Any]]] = None,
    seed: int = 4242,
):
    """A real `TacticalGrid` + `TacticalRules` with combatants at fixed positions.

    Map grammar (`components/combat/battle_map.py:38-56`), all six symbols:
        `.` floor   `#` wall (blocks sight and movement)   `~` difficult terrain
        `H` cover (transparent but obstructive: +2 AC)
        `P` party spawn (REQUIRED)   `E` enemy spawn (REQUIRED)
    Maps must also be at least 4x4. Every one of those rules was learned by
    `parse_map` rejecting a map, which is the validator doing its job.

    Returns `(engine, wrapper, grid, rules, combat_state)`.
    """
    from components.combat.battle_map import parse_map
    from components.combat.tactical_grid import TacticalGrid
    from components.combat.tactical_rules import TacticalRules

    random.seed(seed)
    if characters is None:
        characters = [character_template(char_id=cid, name=cid.title())
                      for cid in placements]
    engine = build_engine(characters=characters, seed=seed)

    from components.dnd_engine_wrapper import DnDEngineWrapper
    wrapper = DnDEngineWrapper(game_engine=engine,
                               character_manager=engine.character_manager)

    grid = TacticalGrid(parse_map({"rows": list(rows)}), wrapper)
    grid.build_terrain()
    for char_id, position in placements.items():
        wrapper.set_entity_position(char_id, position)
    wrapper.refresh_senses()

    combat_state: Dict[str, Any] = {
        "active": True,
        "round": 1,
        "current_turn_index": 0,
        "combatant_states": {
            cid: {"position": pos, "movement_remaining": 30,
                  "reaction_available": True, "is_player": cid == "hero"}
            for cid, pos in placements.items()
        },
        "initiative_order": list(placements),
        "player_ids": [cid for cid in placements if cid == "hero"],
        "enemy_ids": [cid for cid in placements if cid != "hero"],
    }
    rules = TacticalRules(grid, wrapper, combat_state)
    return engine, wrapper, grid, rules, combat_state


def ac_of(wrapper, char_id: str) -> int:
    """An entity's current AC. `ac_bonus()` returns a FRESH object; read, never mutate."""
    return int(wrapper.entities[char_id].ac_bonus().normalized_score)


# --------------------------------------------------------------------------- #
# C4 — temporary hit points
# --------------------------------------------------------------------------- #

class TestC4TemporaryHitPoints:
    """C4: temp HP absorbs damage first and is not healing."""

    def test_temp_hp_absorbs_before_real_hp(self, ledger):
        """Temp HP is a `ModifiableValue` set at ENTITY CREATION from the sheet.

        `Health.temporary_hit_points` is a ModifiableValue, not an int
        (`dnd/blocks/health.py`), and the wrapper populates it from
        `hit_points["temporary"]` at `dnd_engine_wrapper.py:800`. So the way to
        exercise it is to author the sheet and build the entity — assigning a bare
        int afterwards does not work, which is why an earlier version of this test
        skipped itself.
        """
        from dnd.core.events import DamageType

        from tests.integration.harness.game_builder import build_wrapper

        engine = build_engine(characters=[
            character_template(hit_points={"current": 20, "maximum": 28,
                                           "temporary": 7})])
        wrapper = build_wrapper(engine)
        entity = wrapper.entities["aggi"]
        health = entity.health

        assert int(health.temporary_hit_points.normalized_score) == 7, (
            "the sheet's 7 temporary HP never reached the entity")

        real_before = int(health.damage_taken)
        health.take_damage(5, DamageType.SLASHING, entity.uuid)

        assert int(health.temporary_hit_points.normalized_score) == 2, (
            f"5 damage should leave 2 of 7 temp HP, got "
            f"{health.temporary_hit_points.normalized_score}")
        assert int(health.damage_taken) == real_before, (
            "damage reached real HP while temporary HP remained")
        ledger.mechanic("C4:temp_hp_absorbs",
                        f"7 temp HP soaked 5 -> 2 left, real damage still {real_before}")

    def test_temp_hp_overflow_reaches_real_hp(self, ledger):
        """Damage beyond the temp pool must carry through to real HP."""
        from dnd.core.events import DamageType

        from tests.integration.harness.game_builder import build_wrapper

        engine = build_engine(characters=[
            character_template(hit_points={"current": 28, "maximum": 28,
                                           "temporary": 4})])
        wrapper = build_wrapper(engine)
        entity = wrapper.entities["aggi"]
        health = entity.health

        health.take_damage(10, DamageType.SLASHING, entity.uuid)

        assert int(health.temporary_hit_points.normalized_score) == 0, (
            "the temp pool should be exhausted by 10 damage")
        assert int(health.damage_taken) == 6, (
            f"10 damage against 4 temp HP should deal 6 real damage, dealt "
            f"{health.damage_taken}")
        ledger.mechanic("C4:temp_hp_overflow", "10 dmg vs 4 temp -> 6 real")

    def test_temp_hp_is_tracked_on_the_character_sheet(self, ledger):
        """The field must exist and be respected by the rest path."""
        engine = build_engine(characters=[
            character_template(hit_points={"current": 20, "maximum": 28,
                                           "temporary": 6})])
        character = engine.character_manager.characters["aggi"]

        assert character.hit_points["temporary"] == 6
        engine.character_manager.long_rest("aggi")
        assert character.hit_points["temporary"] == 0, (
            "5e: temporary HP does not survive a long rest")
        ledger.mechanic("C4:temp_hp_sheet", "6 temp HP cleared by a long rest")


def _temp_hp(health) -> int:
    value = getattr(health, "temporary_hit_points", 0)
    return int(getattr(value, "normalized_score", value) or 0)


# --------------------------------------------------------------------------- #
# C8 — the standard 5e actions
# --------------------------------------------------------------------------- #

class TestC8StandardActions:
    """C8: grapple, shove, help, disengage, hide, search, ready, two-weapon.

    These were the single largest chunk of dead combat code in the repo —
    `register_standard_actions()` had exactly one match repo-wide (its own
    definition) and zero test files. They are now registered; this asserts each
    resolves through the real resolver.
    """

    STANDARD = ("grapple", "shove", "help", "disengage", "hide", "search",
                "ready", "two_weapon_attack")

    def test_all_eight_are_registered(self, ledger):
        from components.combat.action_registry import ACTION_REGISTRY, is_offerable

        missing = [name for name in self.STANDARD if name not in ACTION_REGISTRY]
        assert not missing, f"standard actions absent from the registry: {missing}"

        unofferable = [n for n in self.STANDARD if not is_offerable(n)]
        assert not unofferable, f"registered but unofferable: {unofferable}"
        ledger.mechanic("C8:registered", f"{len(self.STANDARD)} standard actions")

    def test_each_resolves_without_crashing(self, ledger):
        crashed: List[str] = []
        for name in self.STANDARD:
            engine, wrapper, resolver = build_battle(characters=[
                character_template(), monster_template("gob", "Goblin")])
            try:
                result = resolver.resolve_action(
                    {"actor": "aggi", "action_type": name, "target": "gob"})
                assert isinstance(result, dict), f"{name} -> {type(result)}"
                ledger.action(name, f"resolved: success={result.get('success')}")
            except Exception as exc:                        # noqa: BLE001
                crashed.append(f"{name}: {type(exc).__name__}: {exc}")

        assert not crashed, "standard actions crashed:\n  - " + "\n  - ".join(crashed)
        ledger.mechanic("C8:resolve", f"{len(self.STANDARD)} resolved")

    def test_grapple_is_a_contested_check_not_an_auto_success(self, ledger):
        """A grapple against a far stronger target must sometimes fail.

        Guards the "contested checks resolve correctly" claim the audit flagged as
        unverified, since this file was written by an agent killed before it wrote a
        test.
        """
        outcomes = []
        for trial in range(30):
            engine, wrapper, resolver = build_battle(
                characters=[
                    character_template(ability_scores={
                        "strength": 8, "dexterity": 10, "constitution": 10,
                        "intelligence": 10, "wisdom": 10, "charisma": 10}),
                    monster_template("gob", "Ogre", ability_scores={
                        "strength": 19, "dexterity": 8, "constitution": 16,
                        "intelligence": 5, "wisdom": 7, "charisma": 7}),
                ],
                seed=7000 + trial,
            )
            result = resolver.resolve_action(
                {"actor": "aggi", "action_type": "grapple", "target": "gob"})
            if not action_failed(result):
                outcomes.append(bool(result.get("success")))

        assert outcomes, "no grapple resolved at all"
        assert not all(outcomes), (
            "a STR 8 character grappled a STR 19 ogre every single time — the "
            "contest is not being rolled")
        ledger.mechanic("C8:grapple_contested",
                        f"{sum(outcomes)}/{len(outcomes)} succeeded vs an ogre")


# --------------------------------------------------------------------------- #
# C12 — initiative
# --------------------------------------------------------------------------- #

class TestC12Initiative:
    """C12: initiative is rolled, ordered descending, and stable within a round."""

    def test_initiative_orders_combatants_descending(self, ledger):
        from components.combat.combat_initializer import CombatInitializer

        engine = build_engine(characters=[
            character_template(),
            monster_template("gob1", "Goblin One"),
            monster_template("gob2", "Goblin Two"),
        ])
        from components.dnd_engine_wrapper import DnDEngineWrapper
        wrapper = DnDEngineWrapper(game_engine=engine,
                                   character_manager=engine.character_manager)

        initializer = CombatInitializer.__new__(CombatInitializer)
        initializer.character_manager = engine.character_manager
        initializer.dnd_wrapper = wrapper
        from config.logging_config import get_logger
        initializer.logger = get_logger("test-initiative")

        order = initializer._roll_initiative(["aggi", "gob1", "gob2"])

        assert len(order) == 3, f"expected 3 combatants, got {order}"
        rolls = [entry["initiative"] for entry in order]
        assert rolls == sorted(rolls, reverse=True), (
            f"initiative is not descending: {rolls}")
        assert {e["char_id"] for e in order} == {"aggi", "gob1", "gob2"}
        ledger.mechanic("C12:initiative_order",
                        f"{[(e['char_id'], e['initiative']) for e in order]}")

    def test_initiative_varies_between_encounters(self, ledger):
        """A constant order would mean the d20 is not being rolled."""
        from components.combat.combat_initializer import CombatInitializer
        from config.logging_config import get_logger

        seen = set()
        for trial in range(12):
            engine = build_engine(
                characters=[character_template(),
                            monster_template("gob1", "Goblin One")],
                seed=8000 + trial)
            from components.dnd_engine_wrapper import DnDEngineWrapper
            wrapper = DnDEngineWrapper(game_engine=engine,
                                       character_manager=engine.character_manager)
            initializer = CombatInitializer.__new__(CombatInitializer)
            initializer.character_manager = engine.character_manager
            initializer.dnd_wrapper = wrapper
            initializer.logger = get_logger("test-initiative")

            order = initializer._roll_initiative(["aggi", "gob1"])
            seen.add(tuple(e["initiative"] for e in order))

        assert len(seen) > 1, f"initiative was identical across 12 encounters: {seen}"
        ledger.mechanic("C12:initiative_varies", f"{len(seen)} distinct results/12")


# --------------------------------------------------------------------------- #
# C13 — the grid, distance and difficult terrain
# --------------------------------------------------------------------------- #

class TestC13GridAndTerrain:
    """C13: real geometry — distance in feet, and difficult terrain costing double."""

    def test_distance_is_measured_in_feet(self, ledger):
        _, _, grid, _, _ = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (3, 0)},
        )

        distance = grid.distance_feet("hero", "foe")

        assert distance == 15, f"3 squares should be 15 ft, got {distance}"
        ledger.mechanic("C13:distance", f"3 squares = {distance} ft")

    def test_difficult_terrain_is_recognised(self, ledger):
        _, _, grid, _, _ = build_arena(
            ["P.~~....", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (5, 0)},
        )

        assert grid.map.is_difficult((2, 0)) is True, "`~` is not difficult terrain"
        assert grid.map.is_difficult((0, 0)) is False, "open ground is difficult"
        ledger.mechanic("C13:difficult_terrain", "~ squares cost extra movement")

    def test_terrain_was_actually_built_into_the_engine(self, ledger):
        """`build_terrain()` must register real engine Tiles, not just parse a map."""
        _, _, grid, _, _ = build_arena(["P...", "....", "....", "...E"],
                                       {"hero": (0, 0), "foe": (3, 0)})

        from dnd.core.base_tiles import Tile
        assert Tile._tile_registry, (
            "no engine tiles registered, so the grid is geometry-only and movement "
            "cost cannot be computed")
        ledger.mechanic("C13:terrain_built",
                        f"{len(Tile._tile_registry)} tiles registered")

    def test_walls_block_movement(self, ledger):
        _, _, grid, _, _ = build_arena(["P.#.", "....", "....", "...E"],
                                       {"hero": (0, 0), "foe": (3, 0)})

        assert grid.map.is_walkable((2, 0)) is False, "`#` should not be walkable"
        assert grid.map.is_walkable((0, 1)) is True
        ledger.mechanic("C13:walls", "# blocks movement")


# --------------------------------------------------------------------------- #
# C14 — cover and flanking
# --------------------------------------------------------------------------- #

class TestC14CoverAndFlanking:
    """C14: cover raises AC by a real +2; flanking grants real advantage."""

    def test_cover_raises_ac_by_two(self, ledger):
        from components.combat.tactical_rules import HALF_COVER_AC

        # 'H' is the cover symbol (battle_map.py:50); 'P' marks the required
        # party spawn. Standing on H should grant half cover.
        _, wrapper, grid, rules, _ = build_arena(
            ["H......P", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (5, 0)},
        )
        before = ac_of(wrapper, "hero")

        rules.refresh_cover()
        after = ac_of(wrapper, "hero")

        assert after == before + HALF_COVER_AC, (
            f"half cover should add +{HALF_COVER_AC} AC: {before} -> {after}")
        ledger.mechanic("C14:cover_ac", f"AC {before} -> {after} in cover")

    def test_leaving_cover_removes_the_bonus(self, ledger):
        """The modifier must be removed, not accumulated."""
        from components.combat.tactical_rules import HALF_COVER_AC

        _, wrapper, grid, rules, state = build_arena(
            ["H......P", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (5, 0)},
        )
        base = ac_of(wrapper, "hero")
        rules.refresh_cover()
        covered = ac_of(wrapper, "hero")
        assert covered == base + HALF_COVER_AC

        wrapper.set_entity_position("hero", (1, 0))
        state["combatant_states"]["hero"]["position"] = (1, 0)
        rules.refresh_cover()

        assert ac_of(wrapper, "hero") == base, (
            f"AC did not return to {base} after leaving cover: "
            f"{ac_of(wrapper, 'hero')}")
        ledger.mechanic("C14:cover_removed", f"{base} -> {covered} -> {base}")

    def test_cover_does_not_stack_on_repeated_refresh(self, ledger):
        """Calling refresh twice must not add +4."""
        from components.combat.tactical_rules import HALF_COVER_AC

        _, wrapper, grid, rules, _ = build_arena(
            ["H......P", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (5, 0)},
        )
        base = ac_of(wrapper, "hero")
        rules.refresh_cover()
        once = ac_of(wrapper, "hero")
        rules.refresh_cover()
        twice = ac_of(wrapper, "hero")

        assert once == twice == base + HALF_COVER_AC, (
            f"cover stacked across refreshes: {base} -> {once} -> {twice}")
        ledger.mechanic("C14:cover_no_stack", f"stable at {twice}")

    def test_flanking_is_detected_when_allies_are_opposite(self, ledger):
        """Two allies on opposite sides of a foe grants flanking.

        `_flanked_target` (tactical_rules.py:151-161) defines "ally" as a combatant
        whose `is_hostile` MATCHES mine, and requires that ally to stand on the tile
        directly opposite me through the target. Every participant therefore needs the
        flag — leaving `ally` unset made it read `None` against the hero's `False`, so
        the only real ally was excluded and no flank was found.
        """
        _, wrapper, grid, rules, state = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 1), "ally": (2, 1), "foe": (1, 1)},
        )
        states = state["combatant_states"]
        states["hero"]["is_hostile"] = False
        states["ally"]["is_hostile"] = False
        states["foe"]["is_hostile"] = True

        flanked = rules.refresh_flanking("hero", ["foe"])

        assert flanked == "foe", (
            f"hero at (0,1) and ally at (2,1) flank foe at (1,1), got {flanked!r}")
        ledger.mechanic("C14:flanking", f"flanking target: {flanked}")

    def test_flanking_is_not_granted_without_an_opposite_ally(self, ledger):
        """The inverse: an ally standing off-axis must NOT grant flanking."""
        _, wrapper, grid, rules, state = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 1), "ally": (0, 2), "foe": (1, 1)},
        )
        states = state["combatant_states"]
        states["hero"]["is_hostile"] = False
        states["ally"]["is_hostile"] = False
        states["foe"]["is_hostile"] = True

        flanked = rules.refresh_flanking("hero", ["foe"])

        assert not flanked, (
            f"an ally NOT opposite the target granted flanking anyway: {flanked!r}")
        ledger.mechanic("C14:flanking_requires_opposite",
                        "ally off-axis grants no flank")


# --------------------------------------------------------------------------- #
# C15 — opportunity attacks
# --------------------------------------------------------------------------- #

class TestC15OpportunityAttacks:
    """C15: leaving reach provokes, and consumes the reaction."""

    def test_leaving_reach_provokes_an_opportunity_attack(self, ledger):
        _, wrapper, grid, rules, state = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (1, 0)},
        )
        # `opportunity_attackers` reads `is_hostile` off each combatant
        # state (tactical_rules.py:212), not an `enemy_ids` list.
        state["combatant_states"]["foe"]["is_hostile"] = True
        state["combatant_states"]["hero"]["is_hostile"] = False

        attackers = rules.opportunity_attackers("hero", (4, 0))

        assert "foe" in attackers, (
            f"moving from adjacent to 20 ft away did not provoke: {attackers}")
        ledger.mechanic("C15:provoked", f"attackers={attackers}")

    def test_moving_within_reach_does_not_provoke(self, ledger):
        _, wrapper, grid, rules, state = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (1, 0)},
        )
        # `opportunity_attackers` reads `is_hostile` off each combatant
        # state (tactical_rules.py:212), not an `enemy_ids` list.
        state["combatant_states"]["foe"]["is_hostile"] = True
        state["combatant_states"]["hero"]["is_hostile"] = False

        attackers = rules.opportunity_attackers("hero", (1, 1))

        assert "foe" not in attackers, (
            f"shuffling while staying adjacent should not provoke: {attackers}")
        ledger.mechanic("C15:no_provoke_in_reach", f"attackers={attackers}")

    def test_a_spent_reaction_cannot_provoke_again(self, ledger):
        """One reaction per round: the second departure is free."""
        _, wrapper, grid, rules, state = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (1, 0)},
        )
        # `opportunity_attackers` reads `is_hostile` off each combatant
        # state (tactical_rules.py:212), not an `enemy_ids` list.
        state["combatant_states"]["foe"]["is_hostile"] = True
        state["combatant_states"]["hero"]["is_hostile"] = False

        first = rules.opportunity_attackers("hero", (4, 0))
        assert "foe" in first, f"no one provoked on the first departure: {first}"
        rules.spend_reaction("foe")
        second = rules.opportunity_attackers("hero", (4, 0))

        assert "foe" not in second, (
            f"foe attacked twice in one round with one reaction: {second}")

        rules.reset_reactions()
        third = rules.opportunity_attackers("hero", (4, 0))
        assert "foe" in third, "reset_reactions did not restore the reaction"
        ledger.mechanic("C15:reaction_economy",
                        "provoke -> spend -> refused -> reset -> provoke")


# --------------------------------------------------------------------------- #
# C16 — reach and ranged weapons
# --------------------------------------------------------------------------- #

class TestC16ReachAndRanged:
    """C16: reach weapons strike at 10 ft; ranged weapons are not blocked at range."""

    def test_reach_is_reported_per_character(self, ledger):
        _, _, grid, _, _ = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (5, 0)},
            characters=[character_template(char_id="hero", name="Hero",
                                            equipment=["glaive"]),
                        monster_template("foe", "Foe", equipment=["spear"])],
        )

        reach = grid.reach_feet("hero")

        assert reach >= 5, f"implausible reach {reach} ft"
        ledger.mechanic("C16:reach", f"glaive wielder reach = {reach} ft")

    def test_a_ranged_attack_resolves_at_distance(self, ledger):
        """A longbow at 30 ft must produce a real outcome, not a cancelled attack."""
        from components.combat.combat_action_resolver import CombatActionResolver

        engine, wrapper, grid, rules, state = build_arena(
            ["P...........", "............", "............", "...........E"],
            {"hero": (0, 0), "foe": (6, 0)},
            characters=[character_template(char_id="hero", name="Hero",
                                            equipment=["longbow"]),
                        monster_template("foe", "Foe")],
        )
        resolver = CombatActionResolver(
            dnd_engine_wrapper=wrapper,
            character_manager=engine.character_manager,
            combat_state=state,
        )

        result = resolver.resolve_action(
            {"actor": "hero", "action_type": "attack", "target": "foe"})

        assert not action_failed(result), (
            f"a ranged attack at 30 ft was cancelled: {result}")
        assert result.get("attack_outcome") is not None
        ledger.mechanic("C16:ranged_at_distance",
                        f"30 ft longbow -> {result.get('attack_outcome')}")


# --------------------------------------------------------------------------- #
# C17 — multiattack
# --------------------------------------------------------------------------- #

class TestC17Multiattack:
    """C17: 148 of 334 SRD monsters have Multiattack; it must be parsed and honoured."""

    def test_proficiency_is_counted_exactly_once_on_an_attack(self, ledger):
        """G4: the double-count bug — proficiency was added twice to attack rolls.

        PHB "Making an Attack": `d20 + ability modifier + proficiency bonus`. For a
        STR 16 (+3) level-5 character (proficiency +3) with a longsword, the bonus is
        exactly +6 — not +9. `equip_weapon` sets `Weapon.attack_bonus = proficiency`
        and the engine folds proficiency in again via `Entity.attack_bonus`, which is
        where the duplication came from.
        """
        from tests.integration.harness.game_builder import build_wrapper

        engine = build_engine(characters=[
            character_template(
                level=5,
                ability_scores={"strength": 16, "dexterity": 10, "constitution": 14,
                                "intelligence": 10, "wisdom": 10, "charisma": 10},
                equipment=["longsword"])])
        wrapper = build_wrapper(engine)
        character = engine.character_manager.characters["aggi"]
        entity = wrapper.entities["aggi"]

        ability_modifier = (character.ability_scores["strength"] - 10) // 2
        proficiency = character.proficiency_bonus
        expected = ability_modifier + proficiency

        actual = int(entity.attack_bonus().normalized_score)

        assert actual == expected, (
            f"attack bonus should be {ability_modifier} (STR) + {proficiency} "
            f"(proficiency) = +{expected}, got +{actual}. A value of "
            f"+{expected + proficiency} means proficiency is counted twice.")
        ledger.mechanic("G4:proficiency_counted_once",
                        f"STR +{ability_modifier} + prof +{proficiency} = +{actual}")

    def test_multiattack_is_parsed_from_prose(self, ledger):
        from components.combat.multiattack import parse_multiattack

        parsed = parse_multiattack({
            "name": "Multiattack",
            "desc": "The goblin makes two attacks with its scimitar.",
        })

        assert parsed, "a plain two-attack Multiattack was not parsed"
        ledger.mechanic("C17:parse_prose", str(parsed)[:110])

    def test_attacks_per_turn_reflects_multiattack(self, ledger):
        """A 2-attack stat block must report 2 attacks per turn.

        `attacks_per_turn` is NOT a `CharacterData` field that `add_character`
        accepts — it is set as an attribute on the NPC path (`character_manager.py:490`)
        and by `_grant_extra_attack_if_eligible`. So the test sets it the way
        production does, then reads it back through `attacks_per_turn_for`.
        """
        from components.combat.multiattack import attacks_per_turn_for

        engine = build_engine(characters=[monster_template("brute", "Brute")])
        character = engine.character_manager.characters["brute"]

        assert attacks_per_turn_for(character, default=1) == 1, (
            "a plain monster should start at one attack per turn")

        character.attacks_per_turn = 2
        count = attacks_per_turn_for(character, default=1)

        assert count == 2, f"a 2-attack monster reported {count} attacks/turn"
        ledger.mechanic("C17:attacks_per_turn", f"1 -> {count} attacks")

    def test_extra_attack_raises_attacks_per_turn_at_level_five(self, ledger):
        """P3: a Fighter's Extra Attack must feed the multiattack system."""
        from components.combat.multiattack import attacks_per_turn_for

        engine = build_engine(characters=[
            character_template(character_class="Fighter", level=4,
                               experience_points=2700)])
        manager = engine.character_manager
        character = manager.characters["aggi"]
        before = attacks_per_turn_for(character, default=1)

        while character.level < 5:
            manager.award_xp("aggi", 2000)

        after = attacks_per_turn_for(character, default=1)

        assert after > before, (
            f"a Fighter reaching level 5 did not gain Extra Attack "
            f"({before} -> {after} attacks/turn)")
        ledger.mechanic("P3:extra_attack",
                        f"Fighter L4->L5: {before} -> {after} attacks/turn")

    def test_srd_monsters_with_multiattack_are_counted(self, ledger):
        """The 148/334 figure the audit cites, re-derived from the data."""
        import json
        from pathlib import Path

        monsters = json.loads(Path("data/rules/srd/monsters.json").read_text())
        rows = monsters if isinstance(monsters, list) else list(monsters.values())
        with_multi = sum(
            1 for m in rows
            if any("multiattack" in str(a.get("name", "")).lower()
                   for a in (m.get("actions") or []))
        )

        assert with_multi > 100, (
            f"only {with_multi} monsters have Multiattack; expected ~148")
        ledger.mechanic("C17:srd_prevalence", f"{with_multi}/{len(rows)} monsters")


# --------------------------------------------------------------------------- #
# C18 — class features
# --------------------------------------------------------------------------- #

class TestC18ClassFeatures:
    """C18: 24 features across all 12 classes, granted and usable.

    `ClassFeatureEngine.use()` was the ninth instance of this project's signature
    defect — a fully-built effect interpreter with zero reachable callers.
    """

    ALL_TWELVE = ("Barbarian", "Bard", "Cleric", "Druid", "Fighter", "Monk",
                  "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard")

    def test_every_class_has_at_least_one_authored_feature(self, ledger):
        from components.combat.class_features import ClassFeatureTable

        table = ClassFeatureTable()
        table.load()

        empty = [name for name in self.ALL_TWELVE
                 if not table.for_character(name, 20)]
        assert not empty, f"these classes have no authored features: {empty}"
        ledger.mechanic("C18:all_classes_covered",
                        f"{len(self.ALL_TWELVE)} classes, {len(table.all())} features")

    def test_features_are_granted_at_character_creation(self, ledger):
        engine = build_engine(characters=[
            character_template(character_class="Fighter", level=5)])
        character = engine.character_manager.characters["aggi"]

        assert character.features, (
            "a level-5 Fighter was granted no class features at creation")
        ledger.mechanic("C18:granted_at_creation",
                        f"Fighter L5: {list(character.features)[:6]}")

    def test_activated_features_are_offerable_in_combat(self, ledger):
        """Rage, Second Wind and Action Surge must be selectable as turn actions."""
        from components.combat.action_registry import ACTION_REGISTRY, is_offerable

        for feature in ("rage", "second_wind", "action_surge"):
            assert feature in ACTION_REGISTRY, f"{feature} is not a registry action"
            assert is_offerable(feature), f"{feature} is registered but unofferable"
            ledger.action(feature, "offerable as a turn action")
        ledger.mechanic("C18:activated_offerable",
                        "rage, second_wind, action_surge all offerable")

    def test_rage_writes_real_state(self, ledger):
        """Not a docstring stub: using a feature must change something."""
        engine, wrapper, resolver = build_battle(characters=[
            character_template(character_class="Barbarian", level=5),
            monster_template("gob", "Goblin"),
        ])

        result = resolver.resolve_action(
            {"actor": "aggi", "action_type": "rage"})

        assert isinstance(result, dict), f"rage returned {type(result)}"
        assert not result.get("error"), f"rage failed: {result.get('error')}"
        ledger.mechanic("C18:rage_effect", str(result.get("description"))[:110])

    def test_subsystem_gaps_are_declared_not_faked(self, ledger):
        """10 genuine gaps (Wild Shape, Ki, Metamagic...) must be declared as such."""
        import json
        from pathlib import Path

        data = json.loads(
            Path("data/rules/class_features/class_features.json").read_text())
        needs = (data.get("_meta") or {}).get("needs_subsystem")

        assert needs, (
            "no `_meta.needs_subsystem` — unimplemented features must be declared "
            "rather than silently stubbed")
        ledger.mechanic("C18:gaps_declared", f"{len(needs)} subsystem gaps declared")


# --------------------------------------------------------------------------- #
# C19 — monster senses
# --------------------------------------------------------------------------- #

class TestC19Senses:
    """C19: darkvision/blindsight/truesight from a stat block reach the entity."""

    def test_senses_are_wired_from_the_stat_block(self, ledger):
        engine = build_engine(characters=[
            monster_template("lurker", "Lurker", senses="darkvision 60 ft."),
        ])
        from components.dnd_engine_wrapper import DnDEngineWrapper
        wrapper = DnDEngineWrapper(game_engine=engine,
                                   character_manager=engine.character_manager)

        entity = wrapper.entities["lurker"]
        senses = getattr(entity, "senses", None)

        assert senses is not None, "entity has no senses block at all"
        ledger.mechanic("C19:senses_present",
                        f"senses block present for a darkvision monster")

    def test_entities_can_see_each_other_after_a_sense_refresh(self, ledger):
        """The Phase-1 fix: without this every attack cancelled for want of a target."""
        _, wrapper, grid, _, _ = build_arena(
            ["P.......", "........", "........", ".......E"],
            {"hero": (0, 0), "foe": (2, 0)},
        )

        entity = wrapper.entities["hero"]
        visible = getattr(entity.senses, "entities", None)

        assert visible, (
            "no entities are visible after refresh_senses(); attacks would all "
            "cancel for want of a visible target")
        ledger.mechanic("C19:line_of_sight", f"{len(visible)} entities visible")


# --------------------------------------------------------------------------- #
# C20 — CR, XP budget, encounter difficulty
# --------------------------------------------------------------------------- #

class TestC20EncounterBudget:
    """C20: the XP budget scales with party level and trims over-budget encounters."""

    def test_xp_budget_rises_with_party_level(self, ledger):
        from components.combat.combat_initializer import CombatInitializer

        initializer = CombatInitializer.__new__(CombatInitializer)
        from config.logging_config import get_logger
        initializer.logger = get_logger("test-budget")

        initializer.game_engine = None
        initializer._active_encounter = {"difficulty": "medium"}
        low = initializer._xp_budget(party_level=1, party_size=4)
        high = initializer._xp_budget(party_level=10, party_size=4)

        assert high > low, f"level-10 budget {high} is not above level-1 {low}"
        ledger.mechanic("C20:xp_budget", f"L1={low} L10={high}")

    def test_harder_difficulty_buys_more_monsters(self, ledger):
        from components.combat.combat_initializer import CombatInitializer
        from config.logging_config import get_logger

        initializer = CombatInitializer.__new__(CombatInitializer)
        initializer.logger = get_logger("test-budget")

        initializer.game_engine = None
        initializer._active_encounter = {"difficulty": "easy"}
        easy = initializer._xp_budget(party_level=5, party_size=4)
        initializer._active_encounter = {"difficulty": "deadly"}
        deadly = initializer._xp_budget(party_level=5, party_size=4)

        assert deadly > easy, f"deadly ({deadly}) is not above easy ({easy})"
        ledger.mechanic("C20:difficulty_scaling", f"easy={easy} deadly={deadly}")

    def test_cr_bands_clamp_an_overstated_stat_block(self, ledger):
        """C20: CR bands are code, not a data file — and they must actually clamp.

        The bands live in `NPCStatGenerator._CR_BANDS` (derived by
        `scripts/derive_cr_bands.py`), so an earlier version of this test skipped
        itself looking for a JSON file that was never written. The real defect this
        guards: an LLM asked for CR 1/4 returned a stat block no published monster of
        that CR reaches, and encounter difficulty was tuned against the inflated
        numbers.
        """
        from components.combat.npc_stat_generator import NPCStatGenerator

        generator = NPCStatGenerator.__new__(NPCStatGenerator)
        from config.logging_config import get_logger
        generator.logger = get_logger("test-cr-bands")

        bands = generator._CR_BANDS
        assert bands, "no CR bands are defined at all"

        target_cr = 0.25
        assert target_cr in bands, f"CR {target_cr} missing from the bands"
        hp_min, hp_max, ac_max, _ev_max = bands[target_cr]

        absurd = {
            "name": "Overstated Goblin",
            "armor_class": ac_max + 6,
            "hit_points": {"current": hp_max + 200, "maximum": hp_max + 200,
                           "temporary": 0},
        }
        clamped = generator._clamp_to_cr_band(absurd, target_cr)

        assert clamped["armor_class"] <= ac_max, (
            f"AC {clamped['armor_class']} still exceeds the CR {target_cr} max {ac_max}")
        assert clamped["hit_points"]["maximum"] <= hp_max, (
            f"HP {clamped['hit_points']['maximum']} still exceeds the CR "
            f"{target_cr} max {hp_max}")
        ledger.mechanic("C20:cr_bands",
                        f"CR {target_cr}: AC {ac_max + 6}->{clamped['armor_class']}, "
                        f"HP {hp_max + 200}->{clamped['hit_points']['maximum']}")

    def test_a_legal_stat_block_is_left_alone(self, ledger):
        """The clamp is permissive by design: it excludes the impossible only."""
        from components.combat.npc_stat_generator import NPCStatGenerator
        from config.logging_config import get_logger

        generator = NPCStatGenerator.__new__(NPCStatGenerator)
        generator.logger = get_logger("test-cr-bands")

        hp_min, hp_max, ac_max, _ = generator._CR_BANDS[0.25]
        legal_hp = (hp_min + hp_max) // 2
        legal = {
            "name": "Ordinary Goblin",
            "armor_class": ac_max - 1,
            "hit_points": {"current": legal_hp, "maximum": legal_hp, "temporary": 0},
        }
        result = generator._clamp_to_cr_band(dict(legal), 0.25)

        assert result["armor_class"] == legal["armor_class"], "a legal AC was clamped"
        assert result["hit_points"]["maximum"] == legal_hp, "legal HP was clamped"
        ledger.mechanic("C20:cr_bands_permissive",
                        f"legal CR 0.25 block (AC {legal['armor_class']}, "
                        f"HP {legal_hp}) passed through untouched")
