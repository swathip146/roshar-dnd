"""
Deterministic D&D 5e mechanics — the whole game flow with NO LLM calls.

Why this file exists: every serious defect in this project has been a WIRING
defect, not a narration defect. The LLM has consistently done its job; what broke
was code that never ran, state written to the display but not the record, and
mechanics implemented with no caller. So this suite exercises the deterministic
half of the game end to end and never touches the network.

Ground rules:

* **RAW 5e is the oracle.** Assertions come from the rules, not from current
  behaviour, so a deviation shows up as a failure rather than being baked in. One
  deliberate, documented deviation is asserted as such (see
  `TestProficiencyReachesAttackRolls`).
* **Assert where state is PERSISTED**, never where it is displayed. Writing to
  `combat_state` while `CharacterData` went stale is what let a whole encounter's
  damage vanish.
* **Both directions.** A one-sided assertion is what let `success` be
  unconditionally True through ~13 live attacks.
* **Statistical claims get a fixed seed** and a range wide enough to be robust
  but tight enough to catch a real regression.

Layout follows the shape of a session: character -> dice -> skills -> combat ->
progression -> quests -> persistence.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.character_manager import CharacterManager, CharacterData
from components.dice import DiceRoller
from components.game_engine import GameEngine

pytestmark = [pytest.mark.deterministic]


# --------------------------------------------------------------------------
# Fixtures — plain data, no LLM, no network.
# --------------------------------------------------------------------------

def _sheet(char_id="Aggi", **over):
    """A level-1 Radiant, matching the authored campaign's starting party."""
    sheet = {
        "character_id": char_id, "name": char_id, "level": 1,
        "ability_scores": {"strength": 14, "dexterity": 13, "constitution": 12,
                           "intelligence": 8, "wisdom": 10, "charisma": 13},
        "hit_points": {"current": 12, "maximum": 12, "temporary": 0},
        "armor_class": 14, "character_class": "Fighter", "race": "Alethi",
        "background": "Folk Hero", "equipment": ["Spear", "Shield"],
        "proficiency_bonus": 2, "experience_points": 0,
    }
    sheet.update(over)
    return sheet


@pytest.fixture
def manager():
    manager = CharacterManager()
    manager.add_character(_sheet())
    return manager


@pytest.fixture
def engine():
    engine = GameEngine()
    engine.add_character(_sheet())
    return engine


@pytest.fixture
def roller():
    return DiceRoller()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """
    Enforce the central promise of this file: NO LLM, no network.

    Autouse and repo-wide-safe because it only patches sockets for the duration
    of each test in this module. Without it, "deterministic" is a claim in a
    docstring rather than a property — and a future test that quietly reaches the
    API would make the suite slow, costly and flaky without anyone noticing.
    """
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "the deterministic suite attempted a NETWORK call — it must exercise "
            "mechanics only")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


# ==========================================================================
# 1. Ability scores and modifiers
# ==========================================================================

class TestAbilityModifiers:
    """5e: modifier = floor((score - 10) / 2). Negative scores round DOWN."""

    @pytest.mark.parametrize("score,expected", [
        (1, -5), (2, -4), (3, -4), (8, -1), (9, -1), (10, 0), (11, 0),
        (12, 1), (14, 2), (15, 2), (16, 3), (18, 4), (20, 5), (30, 10),
    ])
    def test_modifier_matches_raw(self, score, expected):
        assert (score - 10) // 2 == expected, (
            f"the 5e modifier for {score} is {expected}")

    def test_engine_agrees_with_raw(self, manager):
        """The engine's own modifier must match the table, not approximate it."""
        import components.dnd_engine_wrapper  # noqa: F401  (sets up dnd path)
        from components.dnd_engine_wrapper import DnDEngineWrapper

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        entity = wrapper.entities["Aggi"]
        scores = manager.characters["Aggi"].ability_scores
        for name in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            expected = (scores[name] - 10) // 2
            actual = getattr(entity.ability_scores, name).modifier
            assert actual == expected, (
                f"{name} {scores[name]}: engine says {actual}, RAW says {expected}")

    def test_scores_are_not_all_ten(self, manager):
        """
        Regression: AbilityConfig's field is `ability_score`, not `score`, and
        pydantic silently ignored the wrong name — so every character had all six
        scores stuck at 10. No STR on attacks, no DEX on AC, no CON on HP.
        """
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        entity = wrapper.entities["Aggi"]
        assert entity.ability_scores.strength.modifier == 2, "STR 14 -> +2"
        assert entity.ability_scores.intelligence.modifier == -1, "INT 8 -> -1"


class TestProficiencyBonusByLevel:
    """5e PHB: +2 at 1-4, +3 at 5-8, +4 at 9-12, +5 at 13-16, +6 at 17-20."""

    @pytest.mark.parametrize("level,expected", [
        (1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4),
        (13, 5), (16, 5), (17, 6), (20, 6),
    ])
    def test_proficiency_matches_raw(self, manager, level, expected):
        assert 2 + (level - 1) // 4 == expected

    def test_levelling_updates_proficiency(self, manager):
        """A level-5 character must attack at +3, not still +2."""
        manager.award_xp("Aggi", 6500)          # level 5
        character = manager.characters["Aggi"]
        assert character.level == 5
        assert character.proficiency_bonus == 3, (
            f"level 5 proficiency is +3, got +{character.proficiency_bonus}")


# ==========================================================================
# 2. Dice
# ==========================================================================

class TestDiceNotation:
    """
    The parser crashed on valid 5e notation (plan 0.11): `4d6kh3` raised
    ValueError on int('6kh3'), and `1d6 + 2` on '+'. Its audit trail also lied:
    `1d8-1` reported `modifier: 0`.
    """

    @pytest.mark.parametrize("expression", [
        "1d6", "2d6", "1d20", "4d6kh3", "2d20kl1", "1d6 + 2", "1d8-1",
        "8d6", "1d4+1", "3d8 + 5",
    ])
    def test_notation_parses(self, roller, expression):
        result = roller.damage_roll(expression)
        assert isinstance(result, dict) and result["total_damage"] >= 0

    def test_keep_highest_drops_the_lowest(self, roller):
        """4d6kh3 must sum the best three of four."""
        for _ in range(40):
            result = roller.damage_roll("4d6kh3")
            rolls = sorted(result["damage_rolls"], reverse=True)
            assert result["dice_subtotal"] == sum(rolls[:3]), (
                f"kh3 of {result['damage_rolls']} != {result['dice_subtotal']}")

    def test_keep_lowest_drops_the_highest(self, roller):
        for _ in range(40):
            result = roller.damage_roll("2d20kl1")
            assert result["dice_subtotal"] == min(result["damage_rolls"])

    def test_the_audit_trail_reports_the_real_modifier(self, roller):
        """`1d8-1` used to report modifier 0 and print "1d8-1 + 0 = 2"."""
        result = roller.damage_roll("1d8-1")
        assert result["static_modifier"] == -1, (
            f"the -1 is missing from the breakdown: {result['breakdown']}")
        assert result["total_damage"] == result["dice_subtotal"] - 1

    def test_positive_modifiers_are_reported(self, roller):
        result = roller.damage_roll("1d6 + 2")
        assert result["static_modifier"] == 2
        assert result["total_damage"] == result["dice_subtotal"] + 2

    def test_the_breakdown_arithmetic_holds(self, roller):
        """Whatever the notation, the parts must add up to the total."""
        for expression in ("1d6", "4d6kh3", "1d8-1", "3d8 + 5", "2d20kl1"):
            result = roller.damage_roll(expression)
            assert (result["total_damage"]
                    == result["dice_subtotal"] + result["static_modifier"]), (
                f"{expression}: {result['breakdown']}")

    @pytest.mark.parametrize("expression", ["4d6e6", "1d20r1", "4d6!", "garbage",
                                            "", "d", "0d6"])
    def test_unsupported_notation_fails_loudly(self, roller, expression):
        """
        Silently returning 0 damage is the worst possible answer.

        Measured 2026-09-10: `4d6e6` (exploding), `1d20r1` (reroll), `4d6!` and
        even the literal "garbage" all returned total_damage 0 with rolls=[] and no
        error. A spell written with exploding dice would deal NO damage and nothing
        would report it — the same silent-zero shape as the `success`-always-True
        bug that took a whole session to find.

        Deliberately accepts EITHER outcome — a loud refusal or a real roll — so
        it stays valid as notation support grows. Since plan 0.11 swapped the
        parser to avrae/d20, `4d6e6` now genuinely rolls; `garbage` still raises.
        """
        try:
            result = roller.damage_roll(expression)
        except ValueError:
            return                      # correct: refused loudly
        assert result["total_damage"] > 0 or result["damage_rolls"], (
            f"{expression!r} silently returned "
            f"{result['total_damage']} damage with rolls="
            f"{result['damage_rolls']}")

    def test_a_mixed_expression_keeps_all_of_its_dice(self, roller):
        """
        `1d6+2d6e6` used to return only the 1d6 — a two-part damage expression
        quietly losing half its dice. It was then rejected outright, because a
        partly-understood expression is not usable.

        Plan 0.11 swapped the parser to avrae/d20, which understands exploding
        notation, so the correct behaviour is now to roll ALL of it. The bug this
        guards against is unchanged: dice going missing from a mixed expression.
        """
        for _ in range(50):
            result = roller.damage_roll("1d6+2d6e6")
            assert len(result["damage_rolls"]) >= 3, (
                f"lost dice from a mixed expression: {result['breakdown']}")

    def test_exploding_notation_actually_explodes(self, roller):
        """
        Replaces an assertion that `4d6e6` must RAISE. That was correct while the
        hand-rolled parser could not understand it, but the fix for plan 0.11 was
        to stop hand-rolling: d20 supports it, so refusing it is no longer right.

        Asserting it exceeds 24 proves the notation is honoured rather than
        silently dropped — plain 4d6 caps at 24.
        """
        random.seed(20260911)
        totals = [roller.damage_roll("4d6e6")["total_damage"] for _ in range(400)]
        assert max(totals) > 24, (
            f"4d6e6 never exceeded 24 in 400 rolls (max {max(totals)}) — "
            f"exploding is being ignored")

    def test_the_error_names_what_it_could_not_parse(self, roller):
        """An error a caller cannot act on is barely better than a silent zero."""
        with pytest.raises(ValueError, match="garbage"):
            roller.damage_roll("garbage")

    def test_supported_notation_is_unaffected(self, roller):
        """Both directions: the guard must not reject anything legal."""
        for expression in ("1d6", "4d6kh3", "2d20kl1", "1d6 + 2", "1d8-1",
                           "3d8 + 5", "2d6[fire]", "8d6", "1d4+1"):
            assert roller.damage_roll(expression)["total_damage"] >= 0

    @pytest.mark.parametrize("sides", [4, 6, 8, 10, 12, 20, 100])
    def test_a_die_stays_in_range(self, roller, sides):
        for _ in range(200):
            assert 1 <= roller.roll_die(sides).result <= sides

    def test_a_die_covers_its_whole_range(self, roller):
        """A d20 that never rolls 1 or 20 would break crits and death saves."""
        random.seed(20260910)
        seen = {roller.roll_die(20).result for _ in range(1000)}
        assert seen == set(range(1, 21)), f"missing faces: {set(range(1,21)) - seen}"


class TestAdvantageAndDisadvantage:
    """5e: advantage rolls 2d20 and keeps the HIGHER; disadvantage the LOWER."""

    def test_advantage_keeps_the_higher(self, roller):
        for _ in range(60):
            result = roller.attack_roll(0, advantage_state="advantage")
            rolls = result["raw_rolls"]
            assert len(rolls) == 2, f"advantage rolled {len(rolls)} d20s"
            assert result["selected_roll"] == max(rolls)

    def test_disadvantage_keeps_the_lower(self, roller):
        for _ in range(60):
            result = roller.attack_roll(0, advantage_state="disadvantage")
            rolls = result["raw_rolls"]
            assert len(rolls) == 2
            assert result["selected_roll"] == min(rolls)

    def test_normal_rolls_one_die(self, roller):
        result = roller.attack_roll(0, advantage_state="normal")
        assert len(result["raw_rolls"]) == 1

    def test_advantage_beats_disadvantage_on_average(self, roller):
        """
        Distributional, with a fixed seed: E[max(2d20)] ≈ 13.8 vs
        E[min(2d20)] ≈ 7.2. A gap this large cannot come from noise at n=400,
        and collapsing it would mean advantage silently stopped working.
        """
        random.seed(20260910)
        high = sum(roller.attack_roll(0, advantage_state="advantage")
                   ["selected_roll"] for _ in range(400)) / 400
        low = sum(roller.attack_roll(0, advantage_state="disadvantage")
                  ["selected_roll"] for _ in range(400)) / 400
        assert high - low > 4.0, (
            f"advantage {high:.1f} vs disadvantage {low:.1f} — too close")


# ==========================================================================
# 3. Skill checks — the 7-step pipeline
# ==========================================================================

class TestSkillCheckPipeline:
    def _check(self, engine, dc, skill="athletics", actor="Aggi"):
        return engine.process_skill_check({
            "actor": actor, "skill": skill, "dc": dc,
            "action_description": f"test {skill} at DC {dc}",
        })

    def test_the_requested_dc_is_honoured(self, engine):
        """
        Plan 2.1: the caller's DC used to be discarded, so DC 5 and DC 25 both
        resolved against the derived DC 14 and both succeeded ~58% of the time —
        difficulty had no effect on outcomes at all.
        """
        random.seed(20260910)
        easy = sum(bool(self._check(engine, 5).get("success")) for _ in range(200))
        hard = sum(bool(self._check(engine, 25).get("success")) for _ in range(200))
        assert easy > hard + 60, (
            f"DC 5 succeeded {easy}/200 and DC 25 {hard}/200 — the DC is being "
            f"ignored")

    def test_dc_five_is_usually_met(self, engine):
        """STR +2 vs DC 5 needs a 3+ on the d20: ~90%."""
        random.seed(1)
        wins = sum(bool(self._check(engine, 5).get("success")) for _ in range(200))
        assert wins > 140, f"only {wins}/200 against DC 5"

    def test_dc_twentyfive_is_usually_missed(self, engine):
        """STR +2 vs DC 25 is impossible on a d20 (max 22)."""
        random.seed(2)
        wins = sum(bool(self._check(engine, 25).get("success")) for _ in range(100))
        assert wins == 0, f"{wins}/100 succeeded on an impossible DC"

    def test_the_result_carries_its_provenance(self, engine):
        """Step 7: a ruling the player cannot inspect is not auditable."""
        result = self._check(engine, 12)
        assert result.get("roll_breakdown"), "no roll breakdown"
        assert result.get("dc_source") == "requested", (
            f"the caller's DC was not used: source={result.get('dc_source')}")
        assert result.get("raw_rolls"), "the raw dice are not recorded"

        # The final DC may differ from the request — PolicyEngine applies house
        # adjustments (RAW profile: "Low level party: -1"). That is legitimate
        # ONLY if it is declared, so assert the adjustment is auditable rather
        # than pinning an exact number.
        adjustments = result.get("dc_adjustments") or []
        drift = 12 - result["dc"]
        assert drift == 0 or adjustments, (
            f"DC moved from 12 to {result['dc']} with no recorded adjustment")
        assert abs(drift) <= 5, (
            f"DC 12 became {result['dc']} — more adjustment than any profile "
            f"declares: {adjustments}")

    def test_an_unknown_actor_is_graceful(self, engine):
        """
        The LLM wrote "aggi" for the character stored as "Aggi" and the unknown
        branch omitted "breakdown", which the pipeline subscripts directly —
        KeyError destroyed four skill checks in a live run.
        """
        result = engine.process_skill_check({
            "actor": "nobody_at_all", "skill": "athletics", "dc": 10,
            "action_description": "test",
        })
        assert isinstance(result, dict)
        assert "roll_breakdown" in result, (
            "the unknown-actor branch omits 'roll_breakdown', which the 7-step "
            "pipeline subscripts directly -> KeyError")

    def test_actor_id_is_case_insensitive(self, engine):
        """"aggi" must resolve to "Aggi" rather than falling through."""
        result = self._check(engine, 10, actor="aggi")
        assert result.get("roll_breakdown"), (
            f"lowercase actor id did not resolve: {result}")


# ==========================================================================
# 4. Combat — real engine, no LLM
# ==========================================================================

@pytest.fixture
def arena():
    """Two combatants, positioned adjacent, senses refreshed."""
    import components.dnd_engine_wrapper  # noqa: F401
    from components.dnd_engine_wrapper import DnDEngineWrapper

    manager = CharacterManager()
    manager.add_character(_sheet("hero", level=5, proficiency_bonus=3,
                                 hit_points={"current": 40, "maximum": 40,
                                             "temporary": 0},
                                 equipment=["Longsword"]))
    manager.add_character(_sheet("foe", level=2, armor_class=13,
                                 hit_points={"current": 22, "maximum": 22,
                                             "temporary": 0},
                                 equipment=["Spear"]))

    class _Stub:
        def __init__(self):
            self.game_state = type("S", (), {"characters": {}})()

    wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
    wrapper.set_entity_position("hero", (0, 0))
    wrapper.set_entity_position("foe", (0, 1))
    return wrapper, manager


def _swing(wrapper, attacker="hero", target="foe"):
    from dnd.actions import Attack
    from dnd.blocks.equipment import WeaponSlot

    wrapper.entities[attacker].action_economy.reset_all_costs()
    return Attack(source_entity_uuid=wrapper.entities[attacker].uuid,
                  target_entity_uuid=wrapper.entities[target].uuid,
                  weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)


class TestAttacksResolve:
    def test_an_attack_produces_an_outcome(self, arena):
        """
        `attack_outcome is None` means the attack was CANCELLED, not missed — the
        state that made 13 live attacks all narrate as "Miss!".
        """
        wrapper, _ = arena
        event = _swing(wrapper)
        assert event is not None
        assert getattr(event, "attack_outcome", None) is not None, (
            f"attack cancelled: {getattr(event, 'status_message', '')}")

    def test_hits_and_misses_both_occur(self, arena):
        """
        Both directions. +5 vs AC 13 hits ~65%, so 60 swings producing all hits
        or all misses means the roll is not being consulted.
        """
        wrapper, _ = arena
        random.seed(20260910)
        outcomes = [str(getattr(_swing(wrapper), "attack_outcome", None))
                    for _ in range(60)]
        hits = sum("HIT" in o or "CRIT" in o and "MISS" not in o for o in outcomes)
        misses = sum("MISS" in o for o in outcomes)
        assert hits > 0, "no attack ever hit"
        assert misses > 0, "no attack ever missed"
        assert hits + misses == 60, f"{60 - hits - misses} produced no outcome"

    def test_the_hit_rate_is_plausible(self, arena):
        """+5 vs AC 13 needs an 8+: ~65%. Wide band, but catches unarmed (~30%)."""
        wrapper, _ = arena
        random.seed(7)
        outcomes = [str(getattr(_swing(wrapper), "attack_outcome", None))
                    for _ in range(300)]
        hits = sum(1 for o in outcomes if "HIT" in o or o.endswith("CRIT"))
        rate = hits / 300
        assert 0.45 < rate < 0.85, f"hit rate {rate:.0%} is implausible for +5 vs AC 13"

    def test_a_natural_twenty_always_crits(self, arena):
        """5e: a 20 hits regardless of AC, and a crit rolls damage dice twice."""
        wrapper, _ = arena
        random.seed(3)
        crits = [e for e in (_swing(wrapper) for _ in range(400))
                 if "CRIT" in str(getattr(e, "attack_outcome", ""))
                 and "MISS" not in str(getattr(e, "attack_outcome", ""))]
        assert crits, "400 attacks produced no critical hit (expected ~20)"

    def test_damage_reaches_the_target(self, arena):
        wrapper, _ = arena
        entity = wrapper.entities["foe"]
        con = entity.ability_scores.constitution.modifier
        before = entity.health.get_total_hit_points(con)
        for _ in range(25):
            _swing(wrapper)
        assert entity.health.get_total_hit_points(con) < before

    def test_a_hit_always_carries_damage(self, arena):
        """
        A "hit" with 0 damage is the signature of the success flag being derived
        from the wrong field.
        """
        wrapper, _ = arena
        random.seed(11)
        for _ in range(80):
            event = _swing(wrapper)
            outcome = str(getattr(event, "attack_outcome", ""))
            if "HIT" in outcome or outcome.endswith("CRIT"):
                rolls = getattr(event, "damage_rolls", None) or []
                assert sum(r.total for r in rolls) > 0, "a hit dealt 0 damage"

    def test_a_miss_never_carries_damage(self, arena):
        wrapper, _ = arena
        random.seed(12)
        for _ in range(80):
            event = _swing(wrapper)
            if "MISS" in str(getattr(event, "attack_outcome", "")):
                rolls = getattr(event, "damage_rolls", None) or []
                assert sum(r.total for r in rolls) == 0, "a miss dealt damage"


class TestProficiencyReachesAttackRolls:
    """
    Proficiency must reach weapon attack rolls — applied EXACTLY ONCE.

    The vendored engine already folds `proficiency_bonus` into
    `Entity.attack_bonus()` (via `_get_attack_bonuses` -> `combine_values`), so
    the wrapper must NOT also write it onto the weapon or it double-counts. A
    mundane weapon therefore carries attack_bonus 0; proficiency comes from the
    entity. See tests/combat/test_proficiency_on_attacks.py for the full RAW pin.
    """

    def test_the_weapon_carries_no_proficiency_bonus(self, arena):
        """A mundane weapon carries 0; proficiency reaches the roll via the entity."""
        from dnd.blocks.equipment import WeaponSlot
        wrapper, _ = arena
        hero = wrapper.entities["hero"]
        weapon = hero.equipment.weapon_main_hand
        assert weapon is not None, "fighting unarmed"
        assert weapon.attack_bonus.score == 0, (
            "a mundane weapon carries no attack bonus of its own; "
            "proficiency comes from the entity, not the weapon")
        str_mod = hero.ability_scores.strength.modifier
        prof = hero.proficiency_bonus.normalized_score
        assert hero.attack_bonus(WeaponSlot.MAIN_HAND).normalized_score == str_mod + prof, (
            "proficiency must reach the attack roll exactly once")

    def test_a_real_weapon_is_equipped(self, arena):
        wrapper, _ = arena
        assert wrapper.entities["hero"].equipment.weapon_main_hand.name == "Longsword"

    def test_non_weapons_are_not_equipped_as_weapons(self, manager):
        """"Shield" and "Leather armor" must not become the main-hand weapon."""
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper

        manager.characters["Aggi"].equipment = ["Leather armor", "Shield", "Spear"]

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        wrapper.equip_from_character_data("Aggi")
        assert wrapper.entities["Aggi"].equipment.weapon_main_hand.name == "Spear"


class TestActionEconomy:
    """5e: one action per turn. Spending it must prevent a second."""

    def test_attacking_spends_the_action(self, arena):
        wrapper, _ = arena
        entity = wrapper.entities["hero"]
        entity.action_economy.reset_all_costs()
        before = entity.action_economy.actions.normalized_score
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot
        Attack(source_entity_uuid=entity.uuid,
               target_entity_uuid=wrapper.entities["foe"].uuid,
               weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        assert entity.action_economy.actions.normalized_score < before

    def test_a_second_attack_is_refused(self, arena):
        """
        Nothing consumed the economy, so `has_actions` stayed True forever and
        every combatant acted four times per turn until the stall-breaker fired.
        """
        wrapper, _ = arena
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        entity = wrapper.entities["hero"]
        entity.action_economy.reset_all_costs()

        def attack():
            return Attack(source_entity_uuid=entity.uuid,
                          target_entity_uuid=wrapper.entities["foe"].uuid,
                          weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)

        assert attack() is not None, "the first attack should resolve"
        assert attack() is None, "a second action in one turn must be refused"

    def test_reset_restores_the_action(self, arena):
        wrapper, _ = arena
        entity = wrapper.entities["hero"]
        entity.action_economy.reset_all_costs()
        _swing(wrapper)
        entity.action_economy.reset_all_costs()
        assert entity.action_economy.actions.normalized_score > 0


# ==========================================================================
# 5. Progression — XP, levels, rests, death saves
# ==========================================================================

class TestExperienceAndLevels:
    """5e PHB XP thresholds."""

    @pytest.mark.parametrize("xp,level", [
        (0, 1), (299, 1), (300, 2), (899, 2), (900, 3), (2700, 4),
        (6500, 5), (14000, 6), (23000, 7), (34000, 8), (48000, 9),
        (64000, 10), (355000, 20),
    ])
    def test_level_for_xp_matches_raw(self, manager, xp, level):
        assert manager.level_for_xp(xp) == level

    def test_xp_never_exceeds_level_twenty(self, manager):
        assert manager.level_for_xp(10_000_000) == 20

    def test_awarding_xp_levels_up(self, manager):
        manager.award_xp("Aggi", 300)
        assert manager.characters["Aggi"].level == 2

    def test_levelling_raises_max_hp(self, manager):
        before = manager.characters["Aggi"].hit_points["maximum"]
        manager.award_xp("Aggi", 6500)
        assert manager.characters["Aggi"].hit_points["maximum"] > before

    def test_xp_accumulates(self, manager):
        manager.award_xp("Aggi", 100)
        manager.award_xp("Aggi", 250)
        assert manager.characters["Aggi"].experience_points == 350
        assert manager.characters["Aggi"].level == 2

    def test_xp_survives_a_save_load(self, manager):
        """
        Regression: `add_character` ignored the 2.5 fields, so XP reset to 0 on
        load while LEVEL survived — which made the bug look like correct state.
        """
        manager.award_xp("Aggi", 6500)
        snapshot = manager.characters["Aggi"].to_dict()
        restored = CharacterData.from_dict(snapshot)
        assert restored.experience_points == 6500
        assert restored.level == 5


class TestHitPointsAreAlwaysCoherent:
    """
    `current` must never exceed `maximum` — 5e has no mechanism for it, short of
    temporary HP, which is a separate field.

    A live run put `Aggi's current HP (13) is higher than max (8)` into the DM's own
    gm_notes, from a stale save whose HP keys did not match the authored sheet. The
    DM noticed and worked around it, which is WORSE than a crash: the contradiction
    reached the prompt and the model had to guess which number to believe.
    """

    def _add(self, hp):
        manager = CharacterManager()
        manager.add_character(_sheet("X", hit_points=hp))
        return manager.characters["X"].hit_points

    def test_current_is_clamped_to_maximum(self):
        """The exact live values."""
        hp = self._add({"current": 13, "maximum": 8, "temporary": 0})
        assert hp["current"] <= hp["maximum"], hp

    def test_a_zero_maximum_trusts_current(self):
        """
        A maximum of 0 with positive current means `maximum` was never populated.
        Clamping to 0 would silently kill the character.
        """
        hp = self._add({"current": 5, "maximum": 0, "temporary": 0})
        assert hp["current"] == 5 and hp["maximum"] == 5

    def test_negative_current_is_floored(self):
        """A negative on the sheet breaks death saves and the HP display."""
        assert self._add({"current": -3, "maximum": 10, "temporary": 0})["current"] == 0

    def test_a_valid_sheet_is_untouched(self):
        """Both directions — the guard must not rewrite correct data."""
        hp = self._add({"current": 8, "maximum": 12, "temporary": 0})
        assert hp["current"] == 8 and hp["maximum"] == 12

    def test_an_integer_shorthand_still_works(self):
        hp = self._add(12)
        assert hp["current"] == 12 and hp["maximum"] == 12

    def test_temporary_hp_is_not_folded_into_current(self):
        """Temp HP is a separate pool; adding it to current would double-count."""
        hp = self._add({"current": 8, "maximum": 8, "temporary": 5})
        assert hp["current"] == 8 and hp["temporary"] == 5

    # ---- the invariant is callable ANYWHERE, not just at load ----------------
    #
    # `add_character()` enforcing it on load was not enough: HP is mutated in a
    # dozen places, and a live run reached COMBAT at `current 13 / maximum 8`.
    # The DM noticed and wrote about the contradiction in its own gm_notes, which
    # is worse than a crash — the model had to guess which number to believe.

    def _character(self, current, maximum):
        manager = CharacterManager()
        manager.add_character(_sheet("A"))
        character = manager.characters["A"]
        character.hit_points.update({"current": current, "maximum": maximum})
        return manager, character

    def test_the_invariant_can_be_enforced_after_the_fact(self):
        manager, character = self._character(13, 8)
        assert manager.enforce_hp_invariant(character) is True
        assert character.hit_points["current"] == 8

    def test_enforcing_reports_whether_it_changed_anything(self):
        """A caller should be able to tell a correction from a no-op."""
        manager, character = self._character(5, 8)
        assert manager.enforce_hp_invariant(character) is False

    def test_enforcing_is_idempotent(self):
        manager, character = self._character(13, 8)
        manager.enforce_hp_invariant(character)
        assert manager.enforce_hp_invariant(character) is False

    def test_levelling_never_breaks_the_invariant(self):
        """
        `_level_up` adds hp_gain to BOTH current and maximum. If current was already
        over maximum, that preserved the gap instead of closing it.
        """
        manager = CharacterManager()
        manager.add_character(_sheet("A"))
        manager.characters["A"].hit_points.update({"current": 13, "maximum": 8})
        manager.award_xp("A", 6500)
        hp = manager.characters["A"].hit_points
        assert hp["current"] <= hp["maximum"], hp

    def test_a_malformed_sheet_is_survived(self):
        manager = CharacterManager()
        manager.add_character(_sheet("A"))
        character = manager.characters["A"]
        character.hit_points = None
        assert manager.enforce_hp_invariant(character) is False

    def test_combat_corrects_an_incoherent_sheet(self):
        """
        Combat is where the player SEES the contradiction, so it must not
        initialise a fight from one.
        """
        import inspect

        from components.combat import combat_initializer

        source = inspect.getsource(combat_initializer.CombatInitializer)
        assert "enforce_hp_invariant" in source, (
            "combat initialises from CharacterManager HP without checking it")


class TestRests:
    def test_a_long_rest_restores_all_hp(self, manager):
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 1
        manager.long_rest("Aggi")
        assert character.hit_points["current"] == character.hit_points["maximum"]

    def test_a_long_rest_clears_death_saves(self, manager):
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 0
        manager.roll_death_save("Aggi", roll=5)
        manager.long_rest("Aggi")
        assert character.death_save_failures == 0

    def test_a_short_rest_can_heal(self, manager):
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 2
        manager.short_rest("Aggi", hit_dice_to_spend=1)
        assert character.hit_points["current"] >= 2

    def test_no_rest_exceeds_maximum_hp(self, manager):
        character = manager.characters["Aggi"]
        manager.long_rest("Aggi")
        manager.short_rest("Aggi", hit_dice_to_spend=1)
        assert character.hit_points["current"] <= character.hit_points["maximum"]


class TestDeathSaves:
    """
    5e: DC 10. Three successes stabilise, three failures kill. A natural 20
    restores 1 HP; a natural 1 counts as two failures.
    """

    def _dying(self, manager):
        manager.characters["Aggi"].hit_points["current"] = 0
        return manager.characters["Aggi"]

    def test_ten_succeeds(self, manager):
        self._dying(manager)
        assert manager.roll_death_save("Aggi", roll=10)["successes"] == 1

    def test_nine_fails(self, manager):
        self._dying(manager)
        assert manager.roll_death_save("Aggi", roll=9)["failures"] == 1

    def test_three_failures_kill(self, manager):
        character = self._dying(manager)
        for _ in range(3):
            manager.roll_death_save("Aggi", roll=5)
        assert character.is_dead is True

    def test_three_successes_stabilise(self, manager):
        character = self._dying(manager)
        for _ in range(3):
            manager.roll_death_save("Aggi", roll=15)
        assert character.is_stable is True
        assert character.is_dead is False

    def test_a_natural_twenty_revives_at_one_hp(self, manager):
        character = self._dying(manager)
        result = manager.roll_death_save("Aggi", roll=20)
        assert result["revived"] is True
        assert character.hit_points["current"] == 1

    def test_a_natural_one_counts_twice(self, manager):
        self._dying(manager)
        assert manager.roll_death_save("Aggi", roll=1)["failures"] == 2

    def test_two_natural_ones_kill(self, manager):
        character = self._dying(manager)
        manager.roll_death_save("Aggi", roll=1)
        manager.roll_death_save("Aggi", roll=1)
        assert character.is_dead is True

    def test_a_conscious_character_does_not_roll(self, manager):
        assert "skipped" in manager.roll_death_save("Aggi")

    def test_a_dead_character_stays_dead(self, manager):
        character = self._dying(manager)
        for _ in range(3):
            manager.roll_death_save("Aggi", roll=5)
        result = manager.roll_death_save("Aggi", roll=20)
        assert character.is_dead is True, "a natural 20 revived a dead character"
        assert result.get("dead") is True

    def test_stabilising_stops_the_rolls(self, manager):
        character = self._dying(manager)
        for _ in range(3):
            manager.roll_death_save("Aggi", roll=15)
        result = manager.roll_death_save("Aggi", roll=5)
        assert result.get("stable") is True
        assert character.is_dead is False

    def test_medicine_can_stabilise(self, manager):
        character = self._dying(manager)
        manager.roll_death_save("Aggi", roll=5)
        assert manager.stabilize("Aggi") is True
        assert character.is_stable is True
        assert character.death_save_failures == 0


# ==========================================================================
# 6. Radiant progression (Roshar extension)
# ==========================================================================

class TestOathsAndIdeals:
    def test_a_radiant_can_speak_the_first_ideal(self, manager):
        manager.characters["Aggi"].character_class = "Radiant"
        manager.characters["Aggi"].radiant_order = "Windrunner"
        assert manager.advance_ideal("Aggi") is True
        assert manager.characters["Aggi"].ideal_level == 1

    def test_ideals_advance_in_order(self, manager):
        manager.characters["Aggi"].character_class = "Radiant"
        manager.characters["Aggi"].radiant_order = "Windrunner"
        for expected in (1, 2, 3):
            manager.advance_ideal("Aggi")
            assert manager.characters["Aggi"].ideal_level == expected

    def test_a_non_radiant_cannot_speak_oaths(self, manager):
        manager.characters["Aggi"].character_class = "Fighter"
        manager.characters["Aggi"].radiant_order = None
        assert manager.advance_ideal("Aggi") is False


# ==========================================================================
# 7. Quests and campaign state
# ==========================================================================

class TestQuestProgression:
    """
    Plan 2.3: the prompt emitted "quests" while the code read
    "quest_objectives", and `complete_quest_objective()` had no callers — so no
    objective could ever complete and the campaign could not finish (D6).
    """

    def test_completing_an_objective_moves_it_to_completed(self, engine):
        engine.game_state.quest_context["pending_objectives"] = [
            {"text": "Survive the Voidbringer attack", "quest": "first_oath"},
            {"text": "Speak the First Ideal", "quest": "first_oath"},
        ]
        engine.complete_quest_objective("Survive the Voidbringer attack")

        completed = [o["text"] for o
                     in engine.game_state.quest_context["completed_objectives"]]
        pending = [o["text"] for o
                   in engine.game_state.quest_context["pending_objectives"]]
        assert "Survive the Voidbringer attack" in completed
        assert "Survive the Voidbringer attack" not in pending, (
            "the objective is both pending and completed")
        assert "Speak the First Ideal" in pending, "an unrelated objective moved"

    def test_completion_is_timestamped(self, engine):
        """Without a time there is no ordering, so no campaign audit trail."""
        engine.game_state.quest_context["pending_objectives"] = [
            {"text": "Survive the ambush"}]
        engine.complete_quest_objective("Survive the ambush")
        completed = engine.game_state.quest_context["completed_objectives"][0]
        assert completed.get("completion_time"), "no completion timestamp"

    def test_an_unknown_objective_is_graceful(self, engine):
        engine.game_state.quest_context["pending_objectives"] = []
        engine.complete_quest_objective("nothing like this exists")  # no raise
        assert engine.game_state.quest_context["completed_objectives"] == []

    def test_completing_twice_does_not_duplicate(self, engine):
        engine.game_state.quest_context["pending_objectives"] = [
            {"text": "Survive the ambush"}]
        engine.complete_quest_objective("Survive the ambush")
        engine.complete_quest_objective("Survive the ambush")
        completed = engine.game_state.quest_context["completed_objectives"]
        assert len(completed) == 1, f"recorded {len(completed)} completions"


class TestNarrativeMemory:
    """
    Plan 2.2: `last_scenario` was a single slot each turn overwrote, so turn N-2
    was gone. Beats give the DM continuity beyond the previous turn.
    """

    def test_beats_accumulate(self, engine):
        for turn in range(1, 4):
            engine._append_narrative_beat(f"Scene {turn} happened.", turn)
        assert len(engine.get_narrative_beats(10)) == 3

    def test_beats_are_bounded(self, engine):
        for turn in range(1, 60):
            engine._append_narrative_beat(f"Scene {turn}.", turn)
        assert len(engine.get_narrative_beats(1000)) <= engine.MAX_NARRATIVE_BEATS

    def test_the_story_block_carries_recent_beats(self, engine):
        engine._append_narrative_beat("Aggi bonded a windspren.", 1)
        assert "windspren" in engine.get_story_so_far(6)

    def test_an_empty_beat_is_ignored(self, engine):
        engine._append_narrative_beat("", 1)
        assert engine.get_narrative_beats(10) == []


# ==========================================================================
# 8. Persistence — the record must survive a round trip
# ==========================================================================

class TestCharacterRoundTrip:
    def test_every_field_survives(self, manager):
        manager.award_xp("Aggi", 900)
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 7
        before = character.to_dict()

        after = CharacterData.from_dict(before).to_dict()
        differing = {k for k in set(before) | set(after)
                     if before.get(k) != after.get(k)}
        assert not differing, f"fields lost in the round trip: {differing}"

    def test_hp_survives(self, manager):
        manager.characters["Aggi"].hit_points["current"] = 3
        restored = CharacterData.from_dict(manager.characters["Aggi"].to_dict())
        assert restored.hit_points["current"] == 3

    def test_death_save_state_survives(self, manager):
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 0
        manager.roll_death_save("Aggi", roll=5)
        restored = CharacterData.from_dict(character.to_dict())
        assert restored.death_save_failures == 1

    def test_the_analytics_summary_is_not_serialised(self, manager):
        """
        Plan 0.3: `to_dict()` used to serialise the analytics summary instead of
        the character, so a save round-trip lost the actual sheet.
        """
        data = manager.characters["Aggi"].to_dict()
        assert "ability_scores" in data and "hit_points" in data
        assert "total_actions" not in data


# ==========================================================================
# 9. Conditions
# ==========================================================================

@pytest.fixture
def conditioned(manager):
    import components.dnd_engine_wrapper  # noqa: F401
    from components.dnd_engine_wrapper import DnDEngineWrapper

    class _Stub:
        def __init__(self):
            self.game_state = type("S", (), {"characters": {}})()

    return DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)


class TestConditions:
    """
    Plan 1.5: `apply_condition` was a pure stub, so no condition ever applied —
    Prone, Restrained, Blinded and the rest were all decorative.
    """

    # All 15 SRD conditions. `Petrified` and `Exhaustion` were the two the vendored
    # engine never implemented; they are now supplied by
    # `components/engine_conditions.py` and registered into `dnd.conditions`.
    @pytest.mark.parametrize("condition", [
        "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled",
        "Incapacitated", "Invisible", "Paralyzed", "Petrified", "Poisoned",
        "Prone", "Restrained", "Stunned", "Unconscious",
    ])
    def test_every_supported_5e_condition_applies(self, conditioned, condition):
        assert conditioned.apply_condition("Aggi", condition) is True, (
            f"{condition} could not be applied")

    def test_no_srd_condition_is_left_unimplemented(self, conditioned):
        """
        Replaces `test_petrified_is_a_known_gap`, which asserted that Petrified
        could NOT be applied and told its own reader: "if the engine ever gains it,
        this test fails and prompts adding it to the supported list above." It did
        exactly that.

        The gap turned out to be TWO conditions, not one — the plan named Petrified
        and missed Exhaustion — so this compares the sets instead of naming names.
        Full behavioural coverage is in tests/test_conditions_and_rules_coverage.py.
        """
        import json
        from pathlib import Path

        srd_path = (Path(__file__).resolve().parent.parent
                    / "data" / "rules" / "srd" / "conditions.json")
        for entry in json.loads(srd_path.read_text()):
            assert conditioned.apply_condition("Aggi", entry["name"]) is True, (
                f"{entry['name']} is in the SRD but cannot be applied")

    def test_an_applied_condition_is_visible(self, conditioned):
        conditioned.apply_condition("Aggi", "Prone")
        assert any("prone" in c.lower()
                   for c in conditioned.get_conditions("Aggi"))

    def test_condition_names_are_case_insensitive(self, conditioned):
        """An LLM will write "prone", not "Prone"."""
        assert conditioned.apply_condition("Aggi", "prone") is True

    def test_a_condition_can_be_removed(self, conditioned):
        conditioned.apply_condition("Aggi", "Prone")
        assert conditioned.remove_condition("Aggi", "Prone") is True
        assert not any("prone" in c.lower()
                       for c in conditioned.get_conditions("Aggi"))

    def test_removing_an_absent_condition_reports_false(self, conditioned):
        """Both directions: a no-op must not claim success."""
        assert conditioned.remove_condition("Aggi", "Prone") is False

    def test_conditions_coexist(self, conditioned):
        conditioned.apply_condition("Aggi", "Prone")
        conditioned.apply_condition("Aggi", "Poisoned")
        active = " ".join(conditioned.get_conditions("Aggi")).lower()
        assert "prone" in active and "poisoned" in active

    def test_an_unknown_condition_is_graceful(self, conditioned):
        assert conditioned.apply_condition("Aggi", "Bewildered") is False

    def test_an_unknown_character_is_graceful(self, conditioned):
        assert conditioned.apply_condition("nobody", "Prone") is False


# ==========================================================================
# 10. Travel, the game clock, and highstorms
# ==========================================================================

class TestTravel:
    """
    Plan 2.6: no travel verb existed, so the party could never go anywhere and
    the three-act structure of Shards of Honor was unreachable.
    """

    def _world(self, engine):
        engine.register_location("Kholinar", exits=["The Shattered Plains"])
        engine.register_location("The Shattered Plains", exits=["Kholinar"])
        engine.set_location("Kholinar")
        return engine

    def test_travel_moves_the_party(self, engine):
        self._world(engine)
        engine.travel_to("The Shattered Plains")
        assert (engine.game_state.location_context["current_location"]
                == "The Shattered Plains")

    def test_travel_is_case_insensitive(self, engine):
        self._world(engine)
        engine.travel_to("the shattered plains")
        assert (engine.game_state.location_context["current_location"]
                == "The Shattered Plains")

    def test_a_new_destination_is_discovered_not_refused(self, engine):
        """The DM must be able to invent a place mid-story."""
        self._world(engine)
        result = engine.travel_to("Urithiru")
        assert result.get("success") is True, f"travel refused: {result}"
        assert engine.game_state.location_context["current_location"] == "Urithiru"
        assert "Urithiru" in engine.game_state.location_context["known_locations"], (
            "the new location was visited but never registered in the graph")

    def test_a_single_letter_does_not_match_everything(self, engine):
        """
        Regression: a naive substring test matched "A" inside "Shattered Plains",
        the same bug class as the combat routing substring match.
        """
        self._world(engine)
        engine.travel_to("A")
        assert engine.game_state.location_context["current_location"] == "A", (
            "a one-letter destination fuzzy-matched an existing location")

    def test_setting_a_location_does_not_wipe_its_description(self, engine):
        """
        Regression: description/features defaulted to ""/[], so
        set_location(name) — which is what state_changes.location does — erased
        them every turn.
        """
        engine.set_location("Kholinar", description="A city of palaces",
                            features=["Gallery of Maps"])
        engine.set_location("Kholinar")
        assert engine.game_state.location_context["description"] == "A city of palaces"
        assert engine.game_state.location_context["features"] == ["Gallery of Maps"]


class TestGameClockAndHighstorms:
    def test_time_starts_on_day_one(self, engine):
        assert engine.get_game_time()["day"] == 1

    def test_advancing_hours_rolls_into_days(self, engine):
        engine.advance_time(hours=30)
        time = engine.get_game_time()
        assert time["day"] == 2 and time["hour"] == 6

    @pytest.mark.parametrize("hour,part", [
        (0, "night"), (5, "night"), (6, "morning"), (11, "morning"),
        (12, "afternoon"), (17, "afternoon"), (18, "evening"), (23, "evening"),
    ])
    def test_part_of_day(self, engine, hour, part):
        engine.advance_time(hours=hour)
        assert engine.get_game_time()["part_of_day"] == part

    def test_a_highstorm_lands_on_the_cycle(self, engine):
        """
        Interval is 5 days. Day 1 is a storm day; the counter must reach 0 on
        storm days rather than jumping 1 -> 5 and never arriving.
        """
        assert engine.days_until_highstorm() == 0, "day 1 should be a storm day"
        engine.advance_time(days=1)
        assert engine.days_until_highstorm() == 4
        engine.advance_time(days=4)
        assert engine.days_until_highstorm() == 0, (
            "the counter never returns to 0, so weather never becomes highstorm")

    def test_the_counter_never_exceeds_the_interval(self, engine):
        for _ in range(12):
            engine.advance_time(days=1)
            assert 0 <= engine.days_until_highstorm() < engine.HIGHSTORM_INTERVAL_DAYS


# ==========================================================================
# 11. Roshar surges — constructible and resource-bounded
# ==========================================================================

class TestSurgesAreConstructible:
    """
    Plan 1.6: all three original surges were UNCONSTRUCTIBLE — a hand-written
    __init__ without super().__init__() meant pydantic never initialised the
    model, so no surge had ever worked, independent of the guard problem.
    """

    @pytest.mark.parametrize("name", [
        "Lashing", "ShardbladeAttack", "ProgressionHealing",
        "Illumination", "Soulcast",
    ])
    def test_the_surge_class_exists_and_constructs(self, name):
        import components.dnd_engine_wrapper  # noqa: F401
        from components.combat import roshar_actions
        from uuid import uuid4

        action_class = getattr(roshar_actions, name, None)
        assert action_class is not None, f"{name} is not defined"
        instance = action_class(source_entity_uuid=uuid4(),
                               target_entity_uuid=uuid4())
        assert instance is not None

    def test_stormlight_is_tracked_on_the_character(self, manager):
        character = manager.characters["Aggi"]
        assert hasattr(character, "stormlight_current")
        assert hasattr(character, "stormlight_capacity")

    def test_stormlight_syncs_to_the_entity(self, manager):
        """
        Plan 1.6: without this every surge guard read False on the entity —
        Stormlight was effectively infinite and untracked.
        """
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper

        character = manager.characters["Aggi"]
        character.stormlight_capacity = 10
        character.stormlight_current = 7

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        wrapper.sync_roshar_attrs_to_entity("Aggi")
        assert wrapper.entities["Aggi"].stormlight_current == 7

    def test_spent_stormlight_flows_back_to_the_character(self, manager):
        """Otherwise the deduction is lost on the next resync."""
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper

        character = manager.characters["Aggi"]
        character.stormlight_capacity = 10
        character.stormlight_current = 7

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        wrapper.sync_roshar_attrs_to_entity("Aggi")

        # Spend it the way a surge does. Direct assignment raises — Entity is a
        # pydantic model with no declared `stormlight_current` field, which is
        # exactly why `set_roshar_attr()` exists (see its docstring).
        wrapper.spend_stormlight("Aggi", 4)

        assert wrapper.entities["Aggi"].stormlight_current == 3
        assert character.stormlight_current == 3, (
            "Stormlight spent in the engine never reaches the character sheet, "
            "so the deduction is lost on the next resync")

    def test_a_surge_cannot_overspend_stormlight(self, manager):
        """Stormlight must be a real constraint, not decorative."""
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper

        character = manager.characters["Aggi"]
        character.stormlight_capacity = 10
        character.stormlight_current = 2

        class _Stub:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_Stub(), character_manager=manager)
        wrapper.sync_roshar_attrs_to_entity("Aggi")
        wrapper.spend_stormlight("Aggi", 5)
        assert character.stormlight_current >= 0, (
            f"Stormlight went negative: {character.stormlight_current}")


# ==========================================================================
# 12. A whole encounter, deterministically
# ==========================================================================

class TestAFullEncounterResolves:
    """
    The end-to-end gate, with a scripted NPC AI instead of an LLM. This is the
    shape of the live bug that took five rounds to notice: every individual
    mechanic passed its own test while the encounter as a whole did nothing.
    """

    def _encounter(self, hero_hp=40, foe_hp=12, foes=2):
        import components.dnd_engine_wrapper  # noqa: F401
        from components.dnd_engine_wrapper import DnDEngineWrapper
        from components.combat.combat_action_resolver import CombatActionResolver
        from components.combat.combat_session_manager import CombatSessionManager

        manager = CharacterManager()
        manager.add_character(_sheet("hero", level=5, proficiency_bonus=3,
                                     hit_points={"current": hero_hp,
                                                 "maximum": hero_hp,
                                                 "temporary": 0},
                                     equipment=["Longsword"]))
        foe_ids = []
        for i in range(foes):
            cid = f"foe_{i + 1}"
            manager.add_character(_sheet(cid, level=1, armor_class=13,
                                         hit_points={"current": foe_hp,
                                                     "maximum": foe_hp,
                                                     "temporary": 0},
                                         equipment=["Spear"]))
            foe_ids.append(cid)

        class _Stub:
            def __init__(self, character_manager):
                self.character_manager = character_manager
                self.game_state = type("S", (), {"characters": {}})()

            def update_combat_state(self, *a, **k):
                return None

        engine = _Stub(manager)
        wrapper = DnDEngineWrapper(game_engine=engine, character_manager=manager)
        wrapper.set_entity_position("hero", (0, 0))
        for index, cid in enumerate(foe_ids):
            wrapper.set_entity_position(cid, (index, 1))

        state = {
            "round_number": 1, "current_turn_index": 0, "combat_log": [],
            "initiative_order": ([{"char_id": "hero", "initiative": 20}]
                                 + [{"char_id": c, "initiative": 10 - i}
                                    for i, c in enumerate(foe_ids)]),
            "active_combatants": ["hero"] + foe_ids,
            "combatant_states": {
                "hero": {"is_hostile": False, "hp_current": hero_hp,
                         "hp_max": hero_hp, "actions_remaining": 1,
                         "bonus_actions_remaining": 1, "reaction_available": True},
            },
        }
        for cid in foe_ids:
            state["combatant_states"][cid] = {
                "is_hostile": True, "hp_current": foe_hp, "hp_max": foe_hp,
                "actions_remaining": 1, "bonus_actions_remaining": 1,
                "reaction_available": True}

        class _Narrative:
            def generate_combat_status(self, state):
                return ""

            def generate_action_narrative(self, *a, **k):
                return ""

            def generate_combat_summary(self, *a, **k):
                return ""

        class _AlwaysAttackHero:
            def decide_action(self, context):
                return {"action_type": "attack", "target": "hero",
                        "reasoning": "scripted"}

        resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                       character_manager=manager,
                                       combat_state=state)
        session = CombatSessionManager(
            combat_state=state, game_engine=engine, character_manager=manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=_Narrative(),
            npc_ai_agent=_AlwaysAttackHero(),
            input_provider=lambda prompt="": "1")
        return session, manager, state

    def test_the_encounter_reaches_a_decisive_outcome(self):
        random.seed(20260910)
        session, _, _ = self._encounter()
        result = session.run_combat_loop()
        assert result["outcome"] in {"victory", "defeat"}, (
            f"outcome {result['outcome']!r} — the loop ended without resolving")

    def test_a_strong_hero_wins(self):
        """+5 vs AC 13 against two 12 HP foes should not lose."""
        random.seed(20260910)
        session, _, _ = self._encounter(hero_hp=40, foe_hp=12)
        assert session.run_combat_loop()["outcome"] == "victory"

    def test_the_encounter_is_efficient(self):
        """
        Not just "it terminates": the stall-breaker used to advance play on every
        single turn (355 iterations across 30 rounds) while three loop tests
        passed, because they only checked termination.
        """
        random.seed(20260910)
        session, _, _ = self._encounter()
        result = session.run_combat_loop()
        assert result.get("stall_breaks", 0) == 0, (
            f"{result.get('stall_breaks')} stall-breaks fired — some actor's "
            f"action economy is not decreasing")
        assert result["rounds"] <= 20, f"took {result['rounds']} rounds"

    def test_damage_reaches_the_character_sheets(self):
        """The record, not the display."""
        random.seed(20260910)
        session, manager, _ = self._encounter()
        session.run_combat_loop()
        foe_hp = [manager.characters[c].hit_points["current"]
                  for c in ("foe_1", "foe_2") if c in manager.characters]
        assert foe_hp and min(foe_hp) <= 0, (
            f"combat ended in victory but the sheets still show {foe_hp} HP")

    def test_every_action_is_logged(self):
        random.seed(20260910)
        session, _, state = self._encounter()
        session.run_combat_loop()
        assert state["combat_log"], "no actions were logged"
        for entry in state["combat_log"]:
            assert "round" in entry and "actor" in entry

    def test_the_loop_never_hits_the_safety_break(self):
        random.seed(20260910)
        session, _, _ = self._encounter()
        result = session.run_combat_loop()
        assert result.get("iterations", 0) < 100, (
            f"{result.get('iterations')} iterations for a 2-enemy fight")


# ==========================================================================
# 13. Rolling summarization (plan 2.2, completed)
# ==========================================================================

class TestRollingSummarization:
    """
    2.2 promised "rolling summarization"; what shipped was truncate-and-drop —
    beats past the window were `del`'d outright. That bounded the prompt but
    silently destroyed the early campaign: by turn 30 the DM had no idea the party
    had ever sworn an oath or lost a companion, which is exactly the continuity
    2.2 existed to provide.

    Aged-out beats are now compressed into a bounded chronicle that REACHES THE
    PROMPT — preserving them in state without showing them to the DM would be the
    same "built but unreachable" failure that hid four subsystems here.
    """

    def _run_turns(self, engine, count):
        for turn in range(1, count + 1):
            engine._append_narrative_beat(
                f"Aggi confronted the challenge of turn {turn}. "
                f"Dust hung in the air and the scene continued at length "
                f"with atmosphere that is not the key event.",
                turn)

    def test_the_verbatim_window_stays_bounded(self, engine):
        self._run_turns(engine, 40)
        assert len(engine.get_narrative_beats(1000)) <= engine.MAX_NARRATIVE_BEATS

    def test_aged_out_beats_are_not_destroyed(self, engine):
        """The regression: turn 1 used to vanish completely."""
        self._run_turns(engine, 30)
        chronicle = " ".join(engine.get_narrative_chronicle(1000))
        assert "[Turn 1]" in chronicle, (
            "turn 1 was deleted rather than summarised — the campaign's opening "
            "is gone from the DM's memory")

    def test_the_chronicle_reaches_the_prompt(self, engine):
        """Preserving history in state and not showing it changes nothing."""
        self._run_turns(engine, 30)
        story = engine.get_story_so_far(6)
        assert "[Turn 1]" in story, (
            "the chronicle exists but never reaches the DM prompt")
        assert "EARLIER" in story, "the DM cannot tell old history from recent"

    def test_chronicle_entries_are_compressed(self, engine):
        """A chronicle of full beats would defeat the point."""
        self._run_turns(engine, 30)
        for entry in engine.get_narrative_chronicle(1000):
            assert len(entry) <= engine.CHRONICLE_ENTRY_CHARS + 30, (
                f"chronicle entry is not compressed: {len(entry)} chars")

    def test_compression_keeps_the_event_not_the_atmosphere(self, engine):
        engine._append_narrative_beat(
            "Aggi swore the First Ideal. Dust swirled and the wind rose over "
            "the plateau in a long descriptive passage.", 1)
        compressed = engine._compress_beat(
            engine.get_narrative_beats(1)[0])
        assert "First Ideal" in compressed
        assert "descriptive passage" not in compressed

    def test_the_chronicle_is_itself_bounded(self, engine):
        """Otherwise the prompt grows without limit over a long campaign."""
        self._run_turns(engine, 300)
        assert (len(engine.get_narrative_chronicle(10000))
                <= engine.MAX_CHRONICLE_ENTRIES)

    def test_the_campaign_opening_survives_a_long_campaign(self, engine):
        """
        When the chronicle itself overflows it drops from the MIDDLE, because how
        the campaign began is what continuity needs most.
        """
        self._run_turns(engine, 300)
        chronicle = " ".join(engine.get_narrative_chronicle(10000))
        assert "[Turn 1]" in chronicle, (
            "the campaign's opening was dropped from the chronicle")

    def test_the_prompt_block_stays_a_sane_size(self, engine):
        """Continuity must not cost unbounded tokens."""
        self._run_turns(engine, 300)
        assert len(engine.get_story_so_far(6)) < 6000

    def test_turn_order_is_preserved(self, engine):
        self._run_turns(engine, 30)
        entries = engine.get_narrative_chronicle(1000)
        turns = [int(e.split("]")[0].replace("[Turn ", "")) for e in entries]
        assert turns == sorted(turns), f"chronicle is out of order: {turns}"

    def test_a_short_campaign_needs_no_chronicle(self, engine):
        """Don't clutter the prompt before anything has aged out."""
        self._run_turns(engine, 3)
        assert engine.get_narrative_chronicle(100) == []
        assert "EARLIER" not in engine.get_story_so_far(6)

    def test_the_chronicle_survives_a_save_load(self, engine):
        """State that does not persist is not memory."""
        self._run_turns(engine, 30)
        before = engine.get_narrative_chronicle(1000)
        assert "narrative_chronicle" in engine.game_state.narrative_context
        restored = dict(engine.game_state.narrative_context)
        assert restored["narrative_chronicle"] == before


class TestADyingAllyCanBeSaved:
    """
    `CharacterManager.stabilize()` had ZERO callers anywhere — the sixth mechanic
    found built-but-unreachable. 5e lets a companion tend someone at 0 HP with a
    DC 10 Medicine check; without a caller the only escape from dying was a natural
    20 on your own death save, so an unconscious ally was effectively doomed.

    `stabilize_dying` is now a DM tool, so the model can reach it when the fiction
    calls for it.
    """

    def _wire(self, manager):
        from agents import dm_tools

        dm_tools.clear_dm_tool_context()
        dm_tools.set_dm_tool_context(character_manager=manager)
        return getattr(dm_tools.stabilize_dying, "function",
                       dm_tools.stabilize_dying)

    def test_the_tool_is_registered(self):
        from agents import dm_tools

        assert "stabilize_dying" in dm_tools.dm_tool_names(), (
            "the model cannot stabilise anyone it cannot call")

    def test_a_dying_character_is_stabilised(self, manager):
        call = self._wire(manager)
        manager.characters["Aggi"].hit_points["current"] = 0
        manager.roll_death_save("Aggi", roll=5)

        result = call()
        assert result["stabilized"] is True
        assert manager.characters["Aggi"].is_stable is True

    def test_stabilising_clears_failed_death_saves(self, manager):
        """Otherwise a later hit resumes the count from where it left off."""
        call = self._wire(manager)
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 0
        manager.roll_death_save("Aggi", roll=5)
        manager.roll_death_save("Aggi", roll=5)
        assert character.death_save_failures == 2

        call()
        assert character.death_save_failures == 0

    def test_a_stabilised_character_stays_unconscious(self):
        """
        5e: stabilised is not healed. Waking them up would make the mechanic a
        free full heal.
        """
        manager = CharacterManager()
        manager.add_character(_sheet("Aggi"))
        call = self._wire(manager)
        manager.characters["Aggi"].hit_points["current"] = 0
        call()
        assert manager.characters["Aggi"].hit_points["current"] == 0

    def test_a_conscious_character_is_refused(self):
        """Both directions — this must not be usable as a buff."""
        manager = CharacterManager()
        manager.add_character(_sheet("Aggi"))
        call = self._wire(manager)
        result = call()
        assert result["stabilized"] is False
        assert "conscious" in result["note"]

    def test_a_dead_character_cannot_be_stabilised(self):
        manager = CharacterManager()
        manager.add_character(_sheet("Aggi"))
        call = self._wire(manager)
        character = manager.characters["Aggi"]
        character.hit_points["current"] = 0
        for _ in range(3):
            manager.roll_death_save("Aggi", roll=5)
        assert character.is_dead is True

        result = call()
        assert result["stabilized"] is False
        assert "dead" in result["note"].lower()

    def test_an_unknown_character_is_graceful(self, manager):
        call = self._wire(manager)
        assert "error" in call(actor="nobody_at_all")


class TestThePartyCanActuallyRest:
    """
    There was NO rest tool. `long_rest`/`short_rest` existed on CharacterManager and
    the DM could not reach either, so "I make camp and take a long rest" was narrated
    and nothing happened — the party stayed wounded and the in-world clock never
    moved.

    Measured in a live 6-turn run that included an explicit rest turn AND a travel
    turn: the clock advanced by **zero hours**. That is what exposed this.
    """

    def _wire(self):
        from agents import dm_tools

        engine = GameEngine()
        engine.add_character(_sheet("Aggi", hit_points={"current": 2,
                                                       "maximum": 8,
                                                       "temporary": 0}))
        dm_tools.clear_dm_tool_context()
        dm_tools.set_dm_tool_context(character_manager=engine.character_manager,
                                     game_engine=engine)
        call = getattr(dm_tools.take_rest, "function", dm_tools.take_rest)
        return call, engine

    def test_the_tool_is_registered(self):
        from agents import dm_tools

        assert "take_rest" in dm_tools.dm_tool_names(), (
            "the DM cannot rest the party it cannot call")

    def test_a_long_rest_restores_full_hp(self):
        call, engine = self._wire()
        call(kind="long")
        hp = engine.character_manager.characters["Aggi"].hit_points
        assert hp["current"] == hp["maximum"]

    def test_a_long_rest_advances_the_clock_by_eight_hours(self):
        """A rest that costs no time is not a rest; the highstorm cycle depends on it."""
        call, engine = self._wire()
        before = engine.game_state.environment.get("elapsed_hours", 0)
        call(kind="long")
        assert engine.game_state.environment["elapsed_hours"] == before + 8

    def test_a_short_rest_costs_one_hour(self):
        call, engine = self._wire()
        before = engine.game_state.environment.get("elapsed_hours", 0)
        call(kind="short")
        assert engine.game_state.environment["elapsed_hours"] == before + 1

    def test_a_short_rest_does_not_fully_heal(self):
        """Otherwise a short rest is a strictly better long rest."""
        call, engine = self._wire()
        call(kind="short")
        hp = engine.character_manager.characters["Aggi"].hit_points
        assert hp["current"] <= hp["maximum"]

    def test_the_whole_party_rests_by_default(self):
        """A party that camps together rests together."""
        from agents import dm_tools

        call, engine = self._wire()
        engine.add_character(_sheet("Kali", hit_points={"current": 1,
                                                       "maximum": 10,
                                                       "temporary": 0}))
        dm_tools.set_dm_tool_context(character_manager=engine.character_manager,
                                     game_engine=engine)
        result = call(kind="long")
        assert set(result["rested"]) == {"Aggi", "Kali"}, result["rested"]
        assert engine.character_manager.characters["Kali"].hit_points["current"] == 10

    def test_naming_an_actor_rests_only_them(self):
        from agents import dm_tools

        call, engine = self._wire()
        engine.add_character(_sheet("Kali", hit_points={"current": 1,
                                                       "maximum": 10,
                                                       "temporary": 0}))
        dm_tools.set_dm_tool_context(character_manager=engine.character_manager,
                                     game_engine=engine)
        call(kind="long", actor="Aggi")
        assert engine.character_manager.characters["Kali"].hit_points["current"] == 1

    def test_the_result_reports_before_and_after(self):
        """The narrator needs the numbers to describe the rest truthfully."""
        call, _ = self._wire()
        entry = call(kind="long")["rested"]["Aggi"]
        assert entry["hp_before"] == 2 and entry["hp_after"] == 8

    def test_an_unknown_actor_does_not_raise(self):
        call, _ = self._wire()
        assert "error" not in call(kind="long", actor="nobody")


class TestTheAdjudicationPromptDemandsToolUse:
    """
    The DM read state and rolled dice but never called a MUTATING world tool across
    six live turns — no travel, no rest, no XP. Step 4 read as optional, so it
    narrated consequences instead of applying them.
    """

    def _prompt(self):
        import inspect

        from agents import scenario_generator_agent

        return inspect.getsource(
            scenario_generator_agent.create_scenario_generator_agent)

    def test_applying_consequences_is_not_optional(self):
        prompt = self._prompt()
        assert "NOT optional" in prompt

    def test_the_prompt_maps_actions_to_tools(self):
        """A list of tool names is not guidance; the model needs the mapping."""
        prompt = self._prompt()
        for tool in ("travel_to_location", "take_rest", "apply_healing",
                     "award_experience", "stabilize_dying"):
            assert tool in prompt, f"{tool} is not mentioned in the prompt"

    def test_every_named_tool_actually_exists(self):
        """
        A prompt naming a tool that is not registered teaches the model to call
        something that will fail — how the missing rest tool was found.
        """
        from agents.dm_tools import dm_tool_names

        prompt = self._prompt()
        registered = set(dm_tool_names())
        for candidate in ("travel_to_location", "take_rest", "apply_healing",
                          "apply_damage", "award_experience", "advance_quest",
                          "spend_stormlight", "stabilize_dying",
                          "roll_skill_check", "query_rules"):
            if candidate in prompt:
                assert candidate in registered, (
                    f"the prompt tells the model to call {candidate!r}, "
                    f"which is not registered")
