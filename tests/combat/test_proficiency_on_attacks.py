"""
Proficiency on WEAPON ATTACK ROLLS: the exact total, not just "is it there".

5e RAW: an attack roll with a weapon you are proficient with is
`d20 + ability modifier + proficiency bonus` (PHB "Making an Attack"). For a
STR 16 (+3) level-5 character (proficiency +3) with a longsword that is exactly
**+6** — no more.

**Why this file exists rather than an attribute check.**
`tests/combat/test_live_combat_bugs.py::test_proficiency_reaches_the_attack_roll`
asserts `weapon.attack_bonus.score == 3`. That is necessary but NOT sufficient:
it proves the wrapper wrote a 3 onto the weapon, and says nothing about what the
d20 roll ends up adding. Two different regressions slip past it:

  1. Proficiency stops reaching the roll (the documented worry).
  2. Proficiency reaches the roll TWICE (what is actually happening).

The vendored engine does NOT ignore proficiency on attacks, contrary to the
comment at the wrapper site. `Entity._get_attack_bonuses` (entity.py) returns
`self.proficiency_bonus` and `Entity.attack_bonus` folds it in via
`proficiency_bonus.combine_values(bonuses)`; `actions.py` then rolls that value
in `Attack.apply`. `actions.py` never NAMES proficiency, which is what the grep
in the wrapper comment observed — but it consumes it through
`source_entity.attack_bonus(...)`. Meanwhile the wrapper ALSO sets
`Weapon.attack_bonus = proficiency` in `equip_weapon`, and the engine adds
`weapon_bonus` too. Both summands are live, so proficiency lands twice.

Measured, as shipped:

    level  1: entity.prof=2 weapon.ab=2 -> roll +7, RAW +5  (excess +2)
    level  5: entity.prof=3 weapon.ab=3 -> roll +9, RAW +6  (excess +3)
    level  9: entity.prof=4 weapon.ab=4 -> roll +11, RAW +7 (excess +4)
    level 17: entity.prof=6 weapon.ab=6 -> roll +15, RAW +9 (excess +6)

The error scales with level, so high-level characters hit far more often than
5e intends. These tests assert the RAW total and a hit rate consistent with it,
so BOTH directions of error fail loudly.

Note `CharacterManager` derives proficiency from level (`2 + (level-1)//4`) and
ignores any `proficiency_bonus` passed in a sheet, so these fixtures set level
and let proficiency follow.
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
from components.dnd_engine_wrapper import DnDEngineWrapper


class _Engine:
    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, level, strength, equipment, ac=14, hp=5000):
    return {
        "character_id": char_id, "name": char_id, "level": level,
        "ability_scores": {"strength": strength, "dexterity": 10,
                           "constitution": 10, "intelligence": 10,
                           "wisdom": 10, "charisma": 10},
        "hit_points": {"current": hp, "maximum": hp, "temporary": 0},
        "armor_class": ac, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": equipment,
    }


def _duel(level=5, strength=16, equipment=("Longsword",), target_ac=14):
    """An attacker and a high-HP dummy, adjacent and able to see each other."""
    manager = CharacterManager()
    manager.add_character(_sheet("Hero", level, strength, list(equipment)))
    manager.add_character(_sheet("Dummy", 1, 10, [], ac=target_ac))

    wrapper = DnDEngineWrapper(game_engine=_Engine(manager),
                               character_manager=manager)
    wrapper.set_entity_position("Hero", (0, 0))
    wrapper.set_entity_position("Dummy", (0, 1))
    wrapper.refresh_senses()
    return wrapper, manager


def _roll_bonus(wrapper, char_id="Hero"):
    """The bonus the engine will actually add to the d20 in Attack.apply."""
    from dnd.blocks.equipment import WeaponSlot

    entity = wrapper.entities[char_id]
    return entity.attack_bonus(WeaponSlot.MAIN_HAND).normalized_score


def _hit_rate(wrapper, trials=1500):
    from dnd.actions import Attack
    from dnd.blocks.equipment import WeaponSlot

    attacker = wrapper.entities["Hero"]
    target = wrapper.entities["Dummy"]
    hits = 0
    for _ in range(trials):
        attacker.action_economy.reset_all_costs()
        event = Attack(source_entity_uuid=attacker.uuid,
                       target_entity_uuid=target.uuid,
                       weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        # CRIT is a hit; matching the substring "HIT" would exclude it.
        if str(getattr(event, "attack_outcome", "")).rsplit(".", 1)[-1] in ("HIT", "CRIT"):
            hits += 1
    return hits / trials


# --------------------------------------------------------------------------

class TestProficiencyIsAppliedExactlyOnce:
    """
    The load-bearing assertions. Each fails if proficiency is DROPPED (the
    documented deviation regressing) and if it is applied TWICE (the live bug).
    """

    def test_attack_bonus_matches_raw_for_a_level_5_fighter(self):
        """STR 16 (+3) + proficiency (+3) = +6. Not +3, not +9."""
        wrapper, manager = _duel(level=5, strength=16)
        proficiency = manager.characters["Hero"].proficiency_bonus
        assert proficiency == 3, "fixture assumption: level 5 is proficiency +3"

        bonus = _roll_bonus(wrapper)
        assert bonus == 3 + proficiency, (
            f"attack roll bonus is +{bonus}; 5e RAW is "
            f"+{3 + proficiency} (STR +3 and proficiency +{proficiency}). "
            f"+3 means proficiency never reached the roll; "
            f"+{3 + 2 * proficiency} means it was added twice.")

    @pytest.mark.parametrize("level,proficiency", [(1, 2), (5, 3), (9, 4), (17, 6)])
    def test_attack_bonus_tracks_proficiency_across_levels(self, level, proficiency):
        """
        Double-counting scales with level, so a single-level check understates
        it. STR 16 (+3) at every level; only proficiency moves.
        """
        wrapper, manager = _duel(level=level, strength=16)
        assert manager.characters["Hero"].proficiency_bonus == proficiency

        bonus = _roll_bonus(wrapper)
        assert bonus == 3 + proficiency, (
            f"level {level}: attack bonus +{bonus}, RAW expects "
            f"+{3 + proficiency} (STR +3 + proficiency +{proficiency})")

    def test_proficiency_is_the_only_source_beyond_the_ability_modifier(self):
        """
        Decompose the sum so a future extra bonus cannot silently stand in for
        proficiency and keep the total looking right.
        """
        from dnd.blocks.equipment import WeaponSlot

        wrapper, manager = _duel(level=5, strength=16)
        entity = wrapper.entities["Hero"]
        pb, weapon_bonus, attack_bonuses, ability_bonuses, _ = \
            entity._get_attack_bonuses(WeaponSlot.MAIN_HAND)

        proficiency = manager.characters["Hero"].proficiency_bonus
        ability = sum(x.normalized_score for x in ability_bonuses)
        extra = weapon_bonus.normalized_score + sum(
            x.normalized_score for x in attack_bonuses)

        assert ability == 3, f"STR 16 should contribute +3, contributed +{ability}"
        assert pb.normalized_score == proficiency, (
            "the engine's own proficiency_bonus is not carrying the character's "
            f"proficiency: {pb.normalized_score} != {proficiency}")
        assert extra == 0, (
            f"+{extra} of unexplained bonus on top of ability and proficiency. "
            "The wrapper writes proficiency onto Weapon.attack_bonus while the "
            "engine already applies Entity.proficiency_bonus, so it is counted "
            "twice.")


class TestProficiencyChangesMeasuredOutcomes:
    """
    Attribute checks alone are not enough: a value can be written and still not
    reach the dice. These assert on observed hit rates.
    """

    def test_hit_rate_matches_the_raw_bonus(self):
        """
        +6 vs AC 14 needs an 8 or better on the d20 = 65%. A +/-6pp window is
        ~4 standard errors at 1500 trials, so this is stable but still excludes
        both +3 (45%) and +9 (85%).
        """
        rate = _hit_rate(_duel(level=5, strength=16)[0])
        assert 0.59 <= rate <= 0.71, (
            f"hit rate {rate:.1%} vs AC 14; +6 (STR +3, proficiency +3) predicts "
            "65%. ~45% means proficiency is missing from the roll, ~85% means it "
            "is applied twice.")

    def test_a_higher_level_character_is_not_wildly_more_accurate(self):
        """
        Between level 1 (+2) and level 17 (+6) RAW moves the hit rate by exactly
        4 points of proficiency = 20pp. Double-counting doubles that to 40pp,
        except it saturates near the top of the d20 — which is precisely how a
        high-level character stops being able to miss.
        """
        low = _hit_rate(_duel(level=1, strength=16)[0])
        high = _hit_rate(_duel(level=17, strength=16)[0])
        delta = high - low
        assert 0.13 <= delta <= 0.27, (
            f"level 1 hit {low:.1%}, level 17 hit {high:.1%} (delta {delta:+.1%}). "
            "Four points of proficiency should be worth about +20pp.")

    def test_an_unarmed_character_gets_no_weapon_proficiency(self):
        """
        Proficiency here is granted for the CARRIED WEAPON. With no weapon there
        is no weapon proficiency to add, so the wrapper must not invent one; the
        roll is ability + the engine's own proficiency only.
        """
        wrapper, manager = _duel(level=5, strength=16, equipment=())
        assert wrapper.entities["Hero"].equipment.weapon_main_hand is None, \
            "fixture assumption: no weapon was equipped"
        bonus = _roll_bonus(wrapper)
        proficiency = manager.characters["Hero"].proficiency_bonus
        assert bonus == 3 + proficiency, (
            f"unarmed attack bonus +{bonus}, expected +{3 + proficiency}")
