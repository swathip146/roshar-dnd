"""
MULTIATTACK: monsters make as many attacks as their stat block grants.

THE BUG THESE TESTS CATCH. `grep -rn multiattack --include="*.py" components/
agents/ core/` returned ZERO production hits, so every monster in the game
attacked exactly ONCE per turn whatever its stat block said. 148 of the 334
vendored SRD monsters have a Multiattack action: an Ape that should throw two
fists threw one, an Owlbear beaked without clawing, and a CR 17 Adult Black
Dragon made a single bite instead of bite + two claws.

That is a BALANCE bug, not a missing nicety. `npc_stat_generator._CR_BANDS` was
derived from these same 334 monsters (`scripts/derive_cr_bands.py`) and encounter
difficulty was tuned against MEASURED time-to-kill, so cutting most monsters'
damage output by half or two thirds made every difficulty figure wrong in the
party's favour.

The root cause was one `continue`: `SRDRules.monster_stats` builds its `attacks`
list only from actions that have an `attack_bonus`, and Multiattack has none.

WHAT IS ASSERTED, AND WHY IT IS ASSERTED THIS WAY:

  * Parsing runs over **the real data/rules/srd/monsters.json**, not fixtures. A
    test over synthetic stat blocks would pass while the shipped data stayed
    broken — precisely how the maneuver gap survived in this repo (see
    test_maneuvers_are_data.py).
  * Combat assertions COUNT THE ATTACK ROLLS ACTUALLY MADE, through the real
    dnd_engine, real resolver and real session manager. "attacks_per_turn == 2"
    on a stat block proves nothing about whether a second attack happens.
  * Unparseable prose must fall back to ONE and WARN. Inventing a plausible count
    is the recurring defect class here (`_meta.correction` in
    data/rules/stormlight/surgebinding.json), and a wrong multiattack count is
    invisible in play while being worth hundreds of percent of a monster's damage.
  * The action economy must still bound the turn: dnd_engine's Attack refuses once
    the pool is empty, which is the only thing stopping infinite attacks, so the
    grant/revoke pairing is tested directly.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.combat_session_manager import CombatSessionManager
from components.combat.multiattack import (MAX_ATTACKS_PER_TURN,
                                           attacks_per_turn_for,
                                           find_multiattack_action,
                                           multiattack_for_monster,
                                           parse_multiattack)
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.srd_rules import get_srd_rules

MONSTERS_JSON = PROJECT_ROOT / "data" / "rules" / "srd" / "monsters.json"

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def raw_monsters():
    """The SHIPPED monster data. Tests must read this, not hand-written stat blocks."""
    monsters = json.loads(MONSTERS_JSON.read_text(encoding="utf-8"))
    log.info("📚 Loaded %d SRD monsters from %s", len(monsters), MONSTERS_JSON.name)
    return monsters


@pytest.fixture(scope="module")
def multiattackers(raw_monsters):
    """Every shipped monster that has a Multiattack action, with its parse."""
    out = [(m["name"], m, multiattack_for_monster(m)) for m in raw_monsters]
    out = [(n, m, r) for n, m, r in out if r is not None]
    log.info("⚔️ %d of %d monsters have Multiattack", len(out), len(raw_monsters))
    return out


# ==========================================================================
# 1. PARSING — over the real shipped data
# ==========================================================================

class TestParseRealSRDData:
    """The parse must work on data/rules/srd/monsters.json as shipped."""

    def test_the_data_actually_contains_multiattack(self, multiattackers):
        """
        Guard the premise. If a future data refresh drops Multiattack entirely,
        every other test here would pass vacuously while monsters silently went
        back to one attack each.
        """
        log.info("Checking that Multiattack exists in the shipped data...")
        assert len(multiattackers) >= 100, (
            f"only {len(multiattackers)} monsters with Multiattack — the SRD "
            f"dataset has 148; did a data refresh drop the action?")

    def test_almost_every_shipped_multiattack_parses(self, multiattackers):
        """
        A parser that fell back for most monsters would 'work' while leaving the
        balance bug in place. 146 of 148 parse; only the Hydra ('as many bite
        attacks as it has heads') and the Violet Fungus ('1d4 Rotting Touch
        attacks') are genuinely variable and must NOT be guessed.
        """
        unparsed = [(n, r["desc"]) for n, _m, r in multiattackers if not r["parsed"]]
        log.info("Parsed %d/%d shipped Multiattack blocks; %d fell back",
                 len(multiattackers) - len(unparsed), len(multiattackers),
                 len(unparsed))
        for name, desc in unparsed:
            log.info("   fallback: %s — %r", name, desc)
        assert len(unparsed) <= 2, f"too many unparsed Multiattacks: {unparsed}"

    def test_every_parsed_count_is_plausible(self, multiattackers):
        """
        No monster may come out at 0 attacks (it would never act) or above the
        published maximum of 7 (the Marilith's six longswords plus its tail).
        A cap set too low is not harmless: it silently demotes the monster to one
        attack, which is what happened to the Marilith during development.
        """
        for name, _m, parsed in multiattackers:
            count = parsed["attacks_per_turn"]
            assert 1 <= count <= MAX_ATTACKS_PER_TURN, \
                f"{name}: implausible attacks_per_turn {count} ({parsed['desc']!r})"
        log.info("All %d parsed counts are within 1..%d",
                 len(multiattackers), MAX_ATTACKS_PER_TURN)

    @pytest.mark.parametrize("monster,expected", [
        # Every number below is read off the shipped desc, not from memory.
        ("Ape", 2),                  # "makes two fist attacks"
        ("Owlbear", 2),              # "one with its beak and one with its claws"
        ("Aboleth", 3),              # "makes three tentacle attacks"
        ("Adult Black Dragon", 3),   # "one with its bite and two with its claws"
        ("Bandit Captain", 3),       # "two with its scimitar and one with its dagger"
        ("Marilith", 7),             # "six with its longswords and one with its tail"
    ])
    def test_named_monsters_get_their_published_count(self, monster, expected):
        """Specific SRD monsters with a known Multiattack get the right number."""
        stats = get_srd_rules().monster_stats(monster)
        log.info("%s: attacks_per_turn=%s (desc: %r)", monster,
                 stats["attacks_per_turn"], (stats["multiattack"] or {}).get("desc"))
        assert stats["attacks_per_turn"] == expected

    @pytest.mark.parametrize("monster", ["Goblin", "Wolf", "Tiger", "Skeleton"])
    def test_monsters_without_multiattack_stay_at_one(self, monster):
        """
        A monster with no Multiattack action must keep the 5e default of exactly
        one attack. Over-applying multiattack would be a worse bug than the one
        being fixed, since it would inflate every low-CR encounter.
        """
        stats = get_srd_rules().monster_stats(monster)
        log.info("%s: attacks_per_turn=%s multiattack=%s", monster,
                 stats["attacks_per_turn"], stats["multiattack"])
        assert stats["multiattack"] is None
        assert stats["attacks_per_turn"] == 1

    def test_ability_entries_do_not_inflate_the_count(self):
        """
        A dragon's Multiattack sequence starts with Frightful Presence, which is
        `"type": "ability"` — not an attack roll. Counting it would give the
        Adult Black Dragon four attacks instead of three.
        """
        parsed = get_srd_rules().monster_stats("Adult Black Dragon")["multiattack"]
        names = [(i["name"], i["type"], i["count"]) for i in parsed["sequence"]]
        log.info("Adult Black Dragon sequence: %s", names)
        assert ("Frightful Presence", "ability", 1) in names
        assert parsed["attacks_per_turn"] == 3

    def test_alternative_option_sets_take_the_strongest(self):
        """
        `action_options` monsters offer alternatives ("three melee attacks ...
        Alternatively, Hurl Flame twice"). Taking the first option would
        under-count the Bandit Captain, whose second option is a weaker ranged
        pair — and under-counting is the very bug being fixed.
        """
        parsed = get_srd_rules().monster_stats("Bandit Captain")["multiattack"]
        log.info("Bandit Captain: source=%s count=%s", parsed["source"],
                 parsed["attacks_per_turn"])
        assert parsed["source"] == "srd_action_options"
        assert parsed["attacks_per_turn"] == 3


class TestUnparseableProseFallsBackAndWarns:
    """Refusing to guess is a feature; the warning is how a gap gets fixed."""

    def test_variable_count_is_not_guessed(self, caplog):
        """
        The Hydra's count depends on its live head count and the Violet Fungus's
        is rolled (1d4). Neither can be a fixed integer, so both must fall back to
        one attack AND say so — a silent guess of 3 or 5 would be undetectable in
        play.
        """
        for monster in ("Hydra", "Violet Fungus"):
            caplog.clear()
            with caplog.at_level(logging.WARNING):
                stats = get_srd_rules().monster_stats(monster)
            log.info("%s -> %s attack(s); warnings: %d", monster,
                     stats["attacks_per_turn"], len(caplog.records))
            assert stats["attacks_per_turn"] == 1
            assert stats["multiattack"]["parsed"] is False
            assert stats["multiattack"]["variable"] is True
            assert any(monster.lower() in r.getMessage().lower()
                       for r in caplog.records), \
                f"the warning must name {monster}"

    def test_unreadable_prose_warns_with_the_text(self, caplog):
        """
        A third-party or LLM stat block whose Multiattack prose we cannot read must
        fall back to one and log BOTH the monster name and the offending text, so
        the gap is fixable rather than merely mysterious.
        """
        prose = "The thing lashes out repeatedly in a whirl of limbs."
        with caplog.at_level(logging.WARNING):
            parsed = parse_multiattack({"name": "Multiattack", "desc": prose},
                                       "Whirling Thing")
        messages = " ".join(r.getMessage() for r in caplog.records)
        log.info("Fallback warning: %s", messages)
        assert parsed["attacks_per_turn"] == 1
        assert parsed["parsed"] is False
        assert "Whirling Thing" in messages
        assert "whirl of limbs" in messages

    def test_prose_only_stat_blocks_still_parse(self):
        """
        The SRD carries structured hints, but LLM-generated NPCs only ever have
        prose. These are the patterns the task names, checked against the wording
        the SRD itself uses.
        """
        cases = {
            "The goblin makes two attacks with its scimitar.": 2,
            "The knight makes two melee attacks.": 2,
            "The bear makes three attacks: one with its bite and two with its claws.": 3,
            "The ape makes two fist attacks.": 2,
        }
        for prose, expected in cases.items():
            parsed = parse_multiattack({"desc": prose}, "Prose Monster")
            log.info("%r -> %s (%s)", prose, parsed["attacks_per_turn"],
                     parsed["source"])
            assert parsed["parsed"] is True
            assert parsed["attacks_per_turn"] == expected

    def test_named_breakdown_survives_the_conjunction(self):
        """
        Regression: the weapon capture used to swallow 'and', so
        'one with its bite and two with its claws' produced a weapon named
        'Bite And'. The count was right but the sequence was junk, which would
        mis-name every narrated attack.
        """
        parsed = parse_multiattack(
            {"desc": "The bear makes three attacks: one with its bite and "
                     "two with its claws."}, "Bear")
        names = [i["name"] for i in parsed["sequence"]]
        log.info("Bear sequence: %s", names)
        assert names == ["Bite", "Claws"]

    def test_a_count_of_zero_or_negative_never_survives(self):
        """A malformed structured hint must not produce a monster that never acts."""
        parsed = parse_multiattack(
            {"desc": "The thing attacks.",
             "actions": [{"action_name": "Claw", "count": 0, "type": "melee"}]},
            "Zero Monster")
        log.info("count=0 -> %s attack(s)", parsed["attacks_per_turn"])
        assert parsed["attacks_per_turn"] == 1

    def test_no_multiattack_action_means_no_multiattack(self):
        """`find_multiattack_action` must not match ordinary weapon actions."""
        assert find_multiattack_action([{"name": "Scimitar"},
                                        {"name": "Shortbow"}]) is None
        assert find_multiattack_action(None) is None
        assert find_multiattack_action([]) is None


class TestAttacksPerTurnAccessor:
    """The accessor the combat layer uses must be defensive about its input."""

    def test_reads_the_field_then_the_block_then_defaults(self):
        assert attacks_per_turn_for({"attacks_per_turn": 3}) == 3
        assert attacks_per_turn_for({"multiattack": {"attacks_per_turn": 2}}) == 2
        assert attacks_per_turn_for({}) == 1
        assert attacks_per_turn_for(None) == 1

    def test_clamps_nonsense(self):
        """
        Garbage in must not become an unbounded turn: a stat block claiming 99
        attacks is a bad parse, and a monster that attacked 99 times would end an
        encounter instantly.
        """
        assert attacks_per_turn_for({"attacks_per_turn": 99}) == MAX_ATTACKS_PER_TURN
        assert attacks_per_turn_for({"attacks_per_turn": 0}) == 1
        assert attacks_per_turn_for({"attacks_per_turn": -4}) == 1
        assert attacks_per_turn_for({"attacks_per_turn": "two"}) == 2
        assert attacks_per_turn_for({"attacks_per_turn": None}) == 1
        assert attacks_per_turn_for({"attacks_per_turn": True}) == 1

    def test_reads_a_character_object_not_just_a_dict(self):
        """
        The session manager holds CharacterData, whose NPC extras are set as plain
        attributes by CharacterManager.add_npc.
        """
        mgr = CharacterManager()
        char_id = mgr.add_npc({
            "name": "Two Fisted Ape", "level": 3,
            "ability_scores": {"strength": 18, "dexterity": 14,
                               "constitution": 14, "intelligence": 6,
                               "wisdom": 12, "charisma": 7},
            "hit_points": {"current": 19, "maximum": 19, "temporary": 0},
            "armor_class": 12, "character_class": "Beast", "race": "Ape",
            "background": "Wild",
            "attacks": [{"name": "Fist", "attack_bonus": 5,
                         "damage_dice": "1d6", "damage_bonus": 3,
                         "damage_type": "bludgeoning"}],
            "attacks_per_turn": 2,
        })
        character = mgr.characters[char_id]
        log.info("add_npc carried attacks_per_turn=%s",
                 getattr(character, "attacks_per_turn", None))
        assert attacks_per_turn_for(character) == 2


# ==========================================================================
# 2. COMBAT — count the attack rolls ACTUALLY made, through the real engine
# ==========================================================================

class _Narrative:
    def generate_combat_status(self, state):
        return f"Round {state['round_number']}"

    def generate_action_narrative(self, *a, **k):
        return "..."


class _StubEngine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


class _AlwaysAttack:
    """Deterministic NPC AI: no LLM, always swing at the hero."""

    def __init__(self, target="hero"):
        self.target = target

    def decide_action(self, context):
        return {"action_type": "attack", "target": self.target}

    run = decide_action


def _build_field(monkeypatch, attacks_per_turn, hero_hp=400, monster_hp=60):
    """
    A real two-combatant encounter: real CharacterManager, real DnDEngineWrapper,
    real CombatActionResolver, real CombatSessionManager. Only the narrator and
    the NPC AI are stubbed, because both would otherwise call an LLM.

    The hero has a large HP pool so damage measurements never tip into death
    saves and end the fight mid-measurement.
    """
    mgr = CharacterManager()
    mgr.add_character({
        "character_id": "hero", "name": "Hero", "level": 5,
        "ability_scores": {"strength": 14, "dexterity": 12,
                           "constitution": 14, "intelligence": 10,
                           "wisdom": 10, "charisma": 10},
        "hit_points": {"current": hero_hp, "maximum": hero_hp, "temporary": 0},
        # Deliberately low AC: the measurement is about how MANY attacks land,
        # so misses are noise we do not want dominating the sample.
        "armor_class": 8, "character_class": "Fighter", "race": "Human",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    })
    monster_id = mgr.add_npc({
        "character_id": "brute", "name": "Brute", "level": 4,
        "ability_scores": {"strength": 18, "dexterity": 12,
                           "constitution": 16, "intelligence": 6,
                           "wisdom": 10, "charisma": 6},
        "hit_points": {"current": monster_hp, "maximum": monster_hp,
                       "temporary": 0},
        "armor_class": 14, "character_class": "Monstrosity", "race": "Brute",
        "background": "Wild", "equipment": ["Spear"], "proficiency_bonus": 2,
        "attacks": [{"name": "Spear", "attack_bonus": 6, "damage_dice": "1d6",
                     "damage_bonus": 4, "damage_type": "piercing"}],
        "attacks_per_turn": attacks_per_turn,
    })

    wrapper = DnDEngineWrapper(game_engine=_StubEngine(), character_manager=mgr)
    wrapper.entities["hero"].position = (0, 0)
    wrapper.entities[monster_id].position = (0, 1)
    wrapper.refresh_senses()

    combat_state = {
        "in_combat": True,
        "active_combatants": ["hero", monster_id],
        "initiative_order": [{"char_id": monster_id, "initiative": 20},
                             {"char_id": "hero", "initiative": 10}],
        "current_turn_index": 0,
        "round_number": 1,
        "combat_log": [],
        "combatant_states": {
            "hero": {"hp_current": hero_hp, "hp_max": hero_hp,
                     "is_hostile": False, "actions_remaining": 1,
                     "bonus_actions_remaining": 1, "reaction_available": True,
                     "conditions": []},
            monster_id: {"hp_current": monster_hp, "hp_max": monster_hp,
                         "is_hostile": True, "actions_remaining": 1,
                         "bonus_actions_remaining": 1,
                         "reaction_available": True, "conditions": []},
        },
        "end_conditions": {"all_hostiles_defeated": False,
                           "all_players_defeated": False},
    }

    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=mgr,
                                    combat_state=combat_state)
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)

    session = CombatSessionManager(
        combat_state=combat_state,
        game_engine=_StubEngine(),
        character_manager=mgr,
        dnd_engine_wrapper=wrapper,
        combat_action_resolver=resolver,
        combat_narrative_generator=_Narrative(),
        npc_ai_agent=_AlwaysAttack(),
        input_provider=lambda prompt: "1",
    )
    return session, wrapper, mgr, monster_id


def _count_attack_events(session, monster_id):
    """
    How many ATTACK EVENTS the monster actually produced.

    Counted off the combat log's real AttackEvents — an attack that was refused
    carries no event, so this measures rolls MADE, not turns taken.
    """
    return sum(1 for entry in session.combat_state["combat_log"]
               if entry["actor"] == monster_id
               and entry["action_type"] in ("attack", "opportunity_attack")
               and entry["result"].get("event") is not None)


def _hero_hp(wrapper):
    entity = wrapper.entities["hero"]
    return wrapper.get_entity_current_hp(entity)


class TestCombatHonoursMultiattack:
    """Count the attack rolls the monster actually makes in a real turn."""

    def test_two_attack_monster_rolls_twice_in_one_turn(self, monkeypatch):
        """
        THE HEADLINE BUG. Before this change `_execute_npc_turn` resolved exactly
        one action and the turn ended, so a stat block granting two attacks
        produced one attack event. Count the events, not the field.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 2)
        session._execute_npc_turn(monster_id)
        made = _count_attack_events(session, monster_id)
        log.info("attacks_per_turn=2 -> %d attack events in one turn", made)
        assert made == 2, f"expected 2 attack rolls, counted {made}"

    def test_three_attack_monster_rolls_three_times(self, monkeypatch):
        """A dragon-shaped three-attack turn, again measured as events."""
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        session._execute_npc_turn(monster_id)
        made = _count_attack_events(session, monster_id)
        log.info("attacks_per_turn=3 -> %d attack events in one turn", made)
        assert made == 3

    def test_monster_without_multiattack_still_attacks_exactly_once(self, monkeypatch):
        """
        The other half of the bug: over-applying multiattack would inflate every
        low-CR encounter. A stat block with no multiattack must produce EXACTLY
        one attack event.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 1)
        session._execute_npc_turn(monster_id)
        made = _count_attack_events(session, monster_id)
        log.info("attacks_per_turn=1 -> %d attack events in one turn", made)
        assert made == 1

    def test_extra_attacks_actually_deal_damage(self, monkeypatch):
        """
        Attack ROLLS are not enough — the damage has to land, or the balance bug
        survives with better logs. Against AC 8 with +6 to hit, two attacks
        across several turns must out-damage one.
        """
        def damage_over(turns, attacks_per_turn):
            session, wrapper, _mgr, monster_id = _build_field(
                monkeypatch, attacks_per_turn)
            start = _hero_hp(wrapper)
            for _ in range(turns):
                session._execute_npc_turn(monster_id)
                session.dnd_wrapper.entities[monster_id] \
                    .action_economy.reset_all_costs()
            return start - _hero_hp(wrapper)

        single = damage_over(12, 1)
        double = damage_over(12, 2)
        log.info("12 turns: 1 attack/turn dealt %d, 2 attacks/turn dealt %d",
                 single, double)
        assert double > single, (
            f"two attacks per turn dealt {double} damage, one dealt {single} — "
            f"the extra attacks are rolling but not landing")

    def test_flurry_stops_when_the_target_drops(self, monkeypatch):
        """
        A monster must not keep beating a corpse. With a 1 HP hero the first hit
        drops them, so the remaining attacks of a 3-attack multiattack are
        abandoned.
        """
        session, wrapper, _mgr, monster_id = _build_field(
            monkeypatch, 3, hero_hp=1)
        session._execute_npc_turn(monster_id)
        made = _count_attack_events(session, monster_id)
        log.info("hero at 1 HP: monster made %d of 3 attacks", made)
        assert made <= 3
        assert _hero_hp(wrapper) <= 0


class TestActionEconomyStillBoundsTheTurn:
    """
    dnd_engine's Attack refuses once the action pool is empty, and that refusal is
    the ONLY thing standing between multiattack and an unbounded turn. These tests
    exist because the fix deliberately GRANTS extra actions.
    """

    def test_turn_ends_with_an_empty_action_pool(self, monkeypatch):
        """
        Every granted action must be spent or revoked. A surplus left in the pool
        would let the turn loop hand the monster another whole turn — the
        `_has_actions_remaining` branch in run_combat_loop.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        session._execute_npc_turn(monster_id)
        economy = wrapper.entities[monster_id].action_economy
        remaining = economy.actions.normalized_score
        log.info("after a 3-attack turn, actions remaining = %s", remaining)
        assert remaining <= 0
        assert session._has_actions_remaining(monster_id) is False

    def test_no_grants_are_left_dangling(self, monkeypatch):
        """
        The grant bookkeeping must be empty after the turn. A leaked modifier
        would silently raise the monster's action budget for the whole encounter.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        session._execute_npc_turn(monster_id)
        leftover = {k: v for k, v in session._extra_action_modifiers.items() if v}
        log.info("dangling multiattack grants: %s", leftover)
        assert leftover == {}

    def test_repeated_turns_do_not_accumulate_actions(self, monkeypatch):
        """
        Ten turns of multiattack must not inflate the pool. If grants accumulated,
        the monster's attacks per turn would grow without bound as the fight went
        on — a slow-motion infinite loop that no single-turn test would catch.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        economy = wrapper.entities[monster_id].action_economy
        base = economy.actions.normalized_score
        per_turn = []
        for _ in range(10):
            economy.reset_all_costs()
            before = _count_attack_events(session, monster_id)
            session._execute_npc_turn(monster_id)
            per_turn.append(_count_attack_events(session, monster_id) - before)
        log.info("base actions=%s, attacks per turn across 10 turns: %s",
                 base, per_turn)
        assert all(count <= 3 for count in per_turn), \
            f"a turn exceeded the stat block's 3 attacks: {per_turn}"

    def test_a_huge_claimed_count_is_clamped_not_obeyed(self, monkeypatch):
        """
        A corrupt stat block claiming 99 attacks must be clamped, not obeyed.
        Obeying it would end any encounter in one turn.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 1)
        session.character_manager.characters[monster_id].attacks_per_turn = 99
        session._execute_npc_turn(monster_id)
        made = _count_attack_events(session, monster_id)
        log.info("claimed 99 attacks -> %d actually made", made)
        assert made <= MAX_ATTACKS_PER_TURN

    def test_non_attack_actions_never_repeat(self, monkeypatch):
        """
        Multiattack grants extra ATTACKS only. A multiattacking monster that
        Dodges must Dodge once — repeating a non-attack action would be a free
        action every turn.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        extra = session._resolve_extra_attacks(
            monster_id, {"actor": monster_id, "action_type": "dodge"},
            {"success": True})
        log.info("dodge produced %d extra attacks", extra)
        assert extra == 0

    def test_a_refused_first_attack_does_not_grant_extras(self, monkeypatch):
        """
        If the engine refused the first swing (no action left), granting actions
        for attacks 2..N would manufacture attacks out of nothing — the exact
        accounting hole the resolver's `refused` flag exists to close.
        """
        session, wrapper, _mgr, monster_id = _build_field(monkeypatch, 3)
        extra = session._resolve_extra_attacks(
            monster_id, {"actor": monster_id, "action_type": "attack",
                         "target": "hero"},
            {"success": False, "refused": True})
        log.info("refused first attack produced %d extra attacks", extra)
        assert extra == 0


# ==========================================================================
# 3. BALANCE — the measurement that makes the bug's size visible
# ==========================================================================

class TestBalanceImpactIsMeasured:
    """
    The point of the fix, stated as a number. Time-to-kill is what the CR bands
    were tuned against, so a multiattacking monster must kill measurably faster.
    """

    def test_multiattack_shortens_time_to_kill(self, monkeypatch):
        """
        Measure rounds-to-drop a party member with 1 vs 2 attacks per turn.
        Averaged over several runs because damage is rolled; a single run of a
        d6+4 spear is far too noisy to assert on.
        """
        def rounds_to_kill(attacks_per_turn, hero_hp=45):
            session, wrapper, _mgr, monster_id = _build_field(
                monkeypatch, attacks_per_turn, hero_hp=hero_hp)
            rounds = 0
            while _hero_hp(wrapper) > 0 and rounds < 60:
                wrapper.entities[monster_id].action_economy.reset_all_costs()
                session._execute_npc_turn(monster_id)
                rounds += 1
            return rounds

        runs = 9
        single = [rounds_to_kill(1) for _ in range(runs)]
        double = [rounds_to_kill(2) for _ in range(runs)]
        mean_single = sum(single) / runs
        mean_double = sum(double) / runs
        log.info("TIME-TO-KILL a 45 HP character (mean of %d runs):", runs)
        log.info("   1 attack/turn : %.1f rounds %s", mean_single, single)
        log.info("   2 attacks/turn: %.1f rounds %s", mean_double, double)
        log.info("   => multiattack made this monster %.2fx faster to kill with",
                 mean_single / max(mean_double, 0.01))
        assert mean_double < mean_single, (
            f"2 attacks/turn took {mean_double:.1f} rounds vs "
            f"{mean_single:.1f} for 1 — multiattack is not increasing DPR")
