"""
The rules a grid makes possible: advantage, cover, flanking, opportunity attacks,
reach, ranged weapons and dash.

None of these existed while combat ran on a two-row line where everyone was
permanently adjacent.

**One upstream engine bug had to be fixed first.**
`Dice._roll_with_advantage` rolled `self.count` dice — 1 for a d20 — and took `max()`
of a single-element list, so ADVANTAGE AND DISADVANTAGE WERE NO-OPS THROUGHOUT THE
ENGINE. Measured before the fix at 2000 attacks: base 45.4%, advantage 45.4%, delta
+0.0% — identical to the decimal, because the same single die was rolled.

That is far bigger than flanking. Advantage is how 5e expresses attacking a Prone or
Restrained target, Dodging, Invisibility, an ally's Help, and several Roshar surges.
All were decorative. Corrected in `components/engine_patches.py`.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.battle_map import parse_map
from components.combat.tactical_grid import TacticalGrid
from components.combat.tactical_rules import HALF_COVER_AC, TacticalRules
from components.dnd_engine_wrapper import DnDEngineWrapper


class _Engine:
    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, **over):
    base = {
        "character_id": char_id, "name": char_id, "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 14, "constitution": 12,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 5000, "maximum": 5000, "temporary": 0},
        "armor_class": 13, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 2,
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def _clean_terrain():
    TacticalGrid._clear_tiles()
    yield
    TacticalGrid._clear_tiles()


def _arena(rows, placements, equipment=None):
    """A grid with combatants at explicit positions."""
    # 600 trials keeps the standard error near 2pp, which is well inside the 10pp
    # margin the advantage test asserts — and keeps this file runnable on every edit.
    manager = CharacterManager()
    for char_id in placements:
        manager.add_character(
            _sheet(char_id, equipment=(equipment or {}).get(char_id, ["Spear"])))

    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                              character_manager=manager)
    grid = TacticalGrid(parse_map({"rows": rows}), wrapper)
    grid.build_terrain()
    for char_id, position in placements.items():
        wrapper.set_entity_position(char_id, position)
    wrapper.refresh_senses()
    return grid, wrapper


def _hit_rate(wrapper, attacker, target, trials=600):
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
        if "HIT" in outcome and "MISS" not in outcome:
            hits += 1
    return hits / trials


# --------------------------------------------------------------------------

class TestAdvantageActuallyChangesTheRoll:
    """
    The engine bug. Without this fix every rule below that grants advantage is
    decorative, and so are Prone, Dodge, Invisible and the surges.
    """

    def test_the_patch_is_applied_on_import(self):
        from components.engine_patches import apply_engine_patches

        assert any("advantage" in name for name in apply_engine_patches())

    def test_advantage_rolls_two_dice(self):
        """
        The direct check: the returned roll list must hold TWO dice per die rolled.
        Before the fix it held one, so max() had nothing to choose between.
        """
        from dnd.core.dice import Dice
        from dnd.core.values import ModifiableValue
        from uuid import uuid4

        bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0,
                                      value_name="test")
        dice = Dice(count=1, value=20, bonus=bonus)
        _, rolls = dice._roll_with_advantage()
        assert len(rolls) == 2, f"advantage rolled {len(rolls)} dice, not 2"

    def test_disadvantage_rolls_two_dice(self):
        from dnd.core.dice import Dice
        from dnd.core.values import ModifiableValue
        from uuid import uuid4

        bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0,
                                      value_name="test")
        _, rolls = Dice(count=1, value=20, bonus=bonus)._roll_with_disadvantage()
        assert len(rolls) == 2

    def test_advantage_keeps_the_higher(self):
        from dnd.core.dice import Dice
        from dnd.core.values import ModifiableValue
        from uuid import uuid4

        bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0,
                                      value_name="test")
        dice = Dice(count=1, value=20, bonus=bonus)
        for _ in range(50):
            best, rolls = dice._roll_with_advantage()
            assert best == max(rolls)

    def test_disadvantage_keeps_the_lower(self):
        from dnd.core.dice import Dice
        from dnd.core.values import ModifiableValue
        from uuid import uuid4

        bonus = ModifiableValue.create(source_entity_uuid=uuid4(), base_value=0,
                                      value_name="test")
        dice = Dice(count=1, value=20, bonus=bonus)
        for _ in range(50):
            worst, rolls = dice._roll_with_disadvantage()
            assert worst == min(rolls)

    def test_advantage_moves_the_hit_rate(self):
        """
        End to end, through a real Attack. 5e predicts roughly +20 percentage points
        for a roll needing a 12+; the band is wide enough to be robust and tight
        enough to catch a no-op.
        """
        from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

        grid, wrapper = _arena(["P...E", "....."] + ["....."] * 2,
                              {"hero": (0, 0), "foe": (1, 0)})
        random.seed(11)
        base = _hit_rate(wrapper, "hero", "foe")

        weapon = wrapper.entities["hero"].equipment.weapon_main_hand
        weapon.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(
            name="flanking", value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=wrapper.entities["hero"].uuid,
            target_entity_uuid=wrapper.entities["hero"].uuid))
        random.seed(11)
        with_advantage = _hit_rate(wrapper, "hero", "foe")

        assert with_advantage - base > 0.10, (
            f"advantage moved the hit rate only {with_advantage - base:+.1%} "
            f"({base:.1%} -> {with_advantage:.1%}); it is still a no-op")


class TestCoverGrantsAC:
    def _rules(self):
        # 'H' at (2,1) is the cover tile.
        grid, wrapper = _arena(["P......E", "..H.....", "........", "........"],
                              {"hero": (0, 1), "foe": (1, 1)})
        state = {"combatant_states": {
            "hero": {"is_hostile": False, "reaction_available": True},
            "foe": {"is_hostile": True, "reaction_available": True}}}
        return TacticalRules(grid, wrapper, state), grid, wrapper

    def test_standing_in_cover_raises_ac(self):
        rules, grid, wrapper = self._rules()
        before = wrapper.entities["foe"].ac_bonus().normalized_score
        grid.move_to("foe", (2, 1), speed_feet=30)
        rules.refresh_cover()
        assert (wrapper.entities["foe"].ac_bonus().normalized_score
                == before + HALF_COVER_AC)

    def test_leaving_cover_removes_it(self):
        """Both directions — a bonus that never expires is a permanent bonus."""
        rules, grid, wrapper = self._rules()
        before = wrapper.entities["foe"].ac_bonus().normalized_score
        grid.move_to("foe", (2, 1), speed_feet=30)
        rules.refresh_cover()
        grid.move_to("foe", (3, 1), speed_feet=30)
        rules.refresh_cover()
        assert wrapper.entities["foe"].ac_bonus().normalized_score == before

    def test_cover_does_not_stack(self):
        """Refreshing twice must not apply +4."""
        rules, grid, wrapper = self._rules()
        before = wrapper.entities["foe"].ac_bonus().normalized_score
        grid.move_to("foe", (2, 1), speed_feet=30)
        rules.refresh_cover()
        rules.refresh_cover()
        rules.refresh_cover()
        assert (wrapper.entities["foe"].ac_bonus().normalized_score
                == before + HALF_COVER_AC)

    def test_cover_makes_the_target_harder_to_hit(self):
        """The point of the +2 — assert on the OUTCOME, not just the number."""
        rules, grid, wrapper = self._rules()
        random.seed(5)
        exposed = _hit_rate(wrapper, "hero", "foe")
        grid.move_to("foe", (1, 0), speed_feet=30)   # stay adjacent, no cover
        grid.move_to("foe", (2, 1), speed_feet=30)   # onto the H tile
        rules.refresh_cover()
        random.seed(5)
        covered = _hit_rate(wrapper, "hero", "foe")
        assert covered < exposed, (
            f"cover did not reduce the hit rate ({exposed:.1%} -> {covered:.1%})")

    def test_clear_all_removes_everything(self):
        """Modifiers live on the entity, which outlives the encounter."""
        rules, grid, wrapper = self._rules()
        before = wrapper.entities["foe"].ac_bonus().normalized_score
        grid.move_to("foe", (2, 1), speed_feet=30)
        rules.refresh_cover()
        rules.clear_all()
        assert wrapper.entities["foe"].ac_bonus().normalized_score == before


class TestFlankingGrantsAdvantage:
    def _rules(self):
        # hero (2,1) | foe (3,1) | ally (4,1)  -> ally is directly opposite
        grid, wrapper = _arena(["........", "PP.....E", "........", "........"],
                              {"hero": (2, 1), "foe": (3, 1), "ally": (4, 1)})
        state = {"combatant_states": {
            "hero": {"is_hostile": False, "reaction_available": True},
            "ally": {"is_hostile": False, "reaction_available": True},
            "foe": {"is_hostile": True, "reaction_available": True}}}
        return TacticalRules(grid, wrapper, state), grid, wrapper

    def test_an_opposite_ally_grants_advantage(self):
        rules, grid, wrapper = self._rules()
        assert rules.refresh_flanking("hero", ["foe"]) == "foe"
        from dnd.core.modifiers import AdvantageStatus

        assert (wrapper.entities["hero"].attack_bonus().advantage
                == AdvantageStatus.ADVANTAGE)

    def test_an_ally_on_the_same_side_does_not(self):
        """
        Both directions. Flanking requires OPPOSITE sides — two allies crowding one
        flank is not a pincer.
        """
        rules, grid, wrapper = self._rules()
        grid.move_to("ally", (2, 0), speed_feet=30)   # beside the hero, not opposite
        assert rules.refresh_flanking("hero", ["foe"]) is None

    def test_flanking_clears_when_the_ally_moves_away(self):
        rules, grid, wrapper = self._rules()
        rules.refresh_flanking("hero", ["foe"])
        grid.move_to("ally", (7, 3), speed_feet=60)
        rules.refresh_flanking("hero", ["foe"])
        from dnd.core.modifiers import AdvantageStatus

        assert (wrapper.entities["hero"].attack_bonus().advantage
                == AdvantageStatus.NONE)

    def test_an_out_of_reach_enemy_is_not_flanked(self):
        """Flanking applies to MELEE attacks, so the target must be in reach."""
        rules, grid, wrapper = self._rules()
        grid.move_to("foe", (7, 1), speed_feet=60)
        assert rules.refresh_flanking("hero", ["foe"]) is None


class TestOpportunityAttacks:
    def _rules(self):
        grid, wrapper = _arena(["P......E", "........", "........", "........"],
                              {"hero": (2, 0), "foe": (3, 0)})
        state = {"combatant_states": {
            "hero": {"is_hostile": False, "reaction_available": True},
            "foe": {"is_hostile": True, "reaction_available": True}}}
        return TacticalRules(grid, wrapper, state), grid, wrapper

    def test_leaving_reach_provokes(self):
        rules, _, _ = self._rules()
        assert rules.opportunity_attackers("hero", (0, 0)) == ["foe"]

    def test_moving_while_staying_adjacent_does_not(self):
        """Both directions: stepping around a foe is free, breaking away is not."""
        rules, _, _ = self._rules()
        assert rules.opportunity_attackers("hero", (3, 1)) == []

    def test_a_spent_reaction_cannot_be_used_again(self):
        """5e: one reaction per round."""
        rules, _, _ = self._rules()
        rules.spend_reaction("foe")
        assert rules.opportunity_attackers("hero", (0, 0)) == []

    def test_reactions_reset(self):
        rules, _, _ = self._rules()
        rules.spend_reaction("foe")
        rules.reset_reactions()
        assert rules.opportunity_attackers("hero", (0, 0)) == ["foe"]

    def test_allies_never_provoke(self):
        rules, _, _ = self._rules()
        rules.combat_state["combatant_states"]["foe"]["is_hostile"] = False
        assert rules.opportunity_attackers("hero", (0, 0)) == []

    def test_a_downed_enemy_does_not_provoke(self):
        rules, _, wrapper = self._rules()
        from dnd.core.modifiers import DamageType

        foe = wrapper.entities["foe"]
        foe.health.take_damage(9000, DamageType.SLASHING, foe.uuid)
        assert rules.opportunity_attackers("hero", (0, 0)) == []


class TestWeaponReachAndRange:
    """
    `_WEAPON_STATS` carried a reach figure for every weapon and NOTHING read it, so a
    halberd struck at 5 ft and a longbow could only be fired at an adjacent target.
    """

    def test_a_reach_weapon_strikes_at_ten_feet(self):
        grid, _ = _arena(["P.E.....", "........", "........", "........"],
                        {"hero": (0, 0), "foe": (2, 0)},
                        equipment={"hero": ["Halberd"]})
        assert grid.reach_feet("hero") == 10
        assert grid.in_melee_reach("hero", "foe")

    def test_a_normal_weapon_does_not(self):
        grid, _ = _arena(["P.E.....", "........", "........", "........"],
                        {"hero": (0, 0), "foe": (2, 0)},
                        equipment={"hero": ["Spear"]})
        assert grid.reach_feet("hero") == 5
        assert not grid.in_melee_reach("hero", "foe")

    def test_a_shardblade_has_reach(self):
        """Roshar-specific and it matters: a Shardblade is enormous."""
        grid, _ = _arena(["P.E.....", "........", "........", "........"],
                        {"hero": (0, 0), "foe": (2, 0)},
                        equipment={"hero": ["Shardblade"]})
        assert grid.reach_feet("hero") == 10

    def test_a_bow_can_be_fired_across_the_map(self):
        """
        Every weapon was built as RangeType.REACH, and `Attack.validate_range` treats
        REACH and RANGE differently — so a longbow at 55 ft was refused with
        "Target entity not in reach".
        """
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        grid, wrapper = _arena(["P" + "." * 10 + "E"] + ["." * 12] * 3,
                              {"archer": (0, 0), "foe": (11, 0)},
                              equipment={"archer": ["Longbow"]})
        assert grid.distance_feet("archer", "foe") == 55

        archer = wrapper.entities["archer"]
        archer.action_economy.reset_all_costs()
        event = Attack(source_entity_uuid=archer.uuid,
                      target_entity_uuid=wrapper.entities["foe"].uuid,
                      weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        assert getattr(event, "attack_outcome", None) is not None, (
            f"the shot was refused: {getattr(event, 'status_message', '')}")

    def test_a_melee_weapon_is_still_refused_at_range(self):
        """Both directions — the fix must not make everything a ranged weapon."""
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        grid, wrapper = _arena(["P" + "." * 10 + "E"] + ["." * 12] * 3,
                              {"hero": (0, 0), "foe": (11, 0)},
                              equipment={"hero": ["Spear"]})
        hero = wrapper.entities["hero"]
        hero.action_economy.reset_all_costs()
        event = Attack(source_entity_uuid=hero.uuid,
                      target_entity_uuid=wrapper.entities["foe"].uuid,
                      weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        assert getattr(event, "attack_outcome", None) is None


class TestDashAddsMovement:
    """`dash` was registered and offerable and added NOTHING, so it wasted the turn."""

    def test_dash_reports_a_bonus(self):
        grid, wrapper = _arena(["P......E", "........", "........", "........"],
                              {"hero": (0, 0), "foe": (7, 0)})
        rules = TacticalRules(grid, wrapper, {"combatant_states": {}})
        assert rules.dash_bonus_feet("hero") == 30

    def test_the_session_manager_applies_it(self):
        """Assert the CALL: a bonus nobody adds is the same as no bonus."""
        import inspect

        from components.combat.combat_session_manager import CombatSessionManager

        source = inspect.getsource(CombatSessionManager._execute_player_turn)
        assert "dash" in source and "dash_bonus_feet" in source
