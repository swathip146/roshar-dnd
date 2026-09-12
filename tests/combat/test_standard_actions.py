"""
The eight PHB actions in `components/combat/standard_actions.py` — Grapple, Shove,
Help, Disengage, Hide, Search, Ready and Two-Weapon fighting — had ZERO coverage and
were never wired into `ACTION_REGISTRY`, so nothing offered them in combat and no test
had ever confirmed their docstrings.

This file does two jobs:

1. **Wiring.** `register_standard_actions()` is now called from `action_registry.py`
   (see the merge next to `ROSHAR_ACTION_ENTRIES`). `TestRegistration` asserts all
   eight are registered, OFFERABLE (nothing needs a caller-supplied parameter — the
   trap that made four of five Surges unplayable) and actually resolve through the
   real `CombatActionResolver`.

2. **Behaviour, treating every docstring as unverified.** Each action is checked
   against what 5e actually promises, on observable state rather than status strings:
   a contested check resolves with the RIGHT abilities and applies its condition only
   on a win; Help grants MEASURABLE advantage on the ally's next attack and then
   expires; Disengage suppresses a REAL opportunity attack computed by
   `TacticalRules.opportunity_attackers`; Hide/Search/Ready/Two-Weapon behave per PHB.

Contested outcomes are made deterministic by pinning the d20 to a constant and letting
the ability gap decide, so "the attacker wins" and "the attacker loses" are both real,
repeatable assertions rather than coin flips.
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

from config.logging_config import get_logger

# Importing the wrapper applies `apply_engine_patches()` (module scope), which fixes
# `Dice._roll_with_advantage` — WITHOUT it Help's advantage rolls one die and is
# decorative, so this import is load-bearing for the Help measurement below.
from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.battle_map import BattleMap
from components.combat.tactical_grid import TacticalGrid
from components.combat.tactical_rules import TacticalRules
from components.combat.action_registry import (ACTION_REGISTRY, is_offerable,
                                               offerable_actions)
import components.combat.standard_actions as sa

from dnd.actions import Attack, WeaponSlot
from dnd.core.dice import AttackOutcome

logger = get_logger(__name__)

STANDARD_ACTIONS = ("grapple", "shove", "help", "disengage", "hide", "search",
                    "ready", "two_weapon_attack")

# Ability score presets. A big gap makes a pinned-d20 contest deterministic.
STRONG = {"strength": 20, "dexterity": 10, "constitution": 14,
          "intelligence": 10, "wisdom": 16, "charisma": 10}
FEEBLE = {"strength": 3, "dexterity": 3, "constitution": 10,
          "intelligence": 10, "wisdom": 6, "charisma": 10}
NIMBLE = {"strength": 3, "dexterity": 20, "constitution": 10,
          "intelligence": 10, "wisdom": 6, "charisma": 10}
BRUTE = {"strength": 20, "dexterity": 3, "constitution": 14,
         "intelligence": 10, "wisdom": 10, "charisma": 10}
HAWKEYE = {"strength": 10, "dexterity": 10, "constitution": 10,
           "intelligence": 10, "wisdom": 20, "charisma": 10}


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _sheet(char_id, scores, equipment=("Spear",), **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": dict(scores),
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 14, "character_class": "Fighter", "race": "Alethi",
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


def _build(specs, overrides=None):
    """
    Build a wrapper with the named characters, one grid square apart on a line.

    `specs` is a list of (char_id, ability_scores, equipment) tuples. `overrides` is
    an optional {char_id: {extra sheet kwargs}} — used to raise a target's AC so a
    hit-rate measurement lands in the mid-range where advantage is measurable rather
    than pinned against the ceiling. Returns (character_manager, wrapper,
    {char_id: entity}).
    """
    overrides = overrides or {}
    manager = CharacterManager()
    for char_id, scores, equipment in specs:
        manager.add_character(_sheet(char_id, scores, equipment=equipment,
                                     **overrides.get(char_id, {})))
    wrapper = DnDEngineWrapper(game_engine=_Engine(manager), character_manager=manager)
    for index, (char_id, _, _) in enumerate(specs):
        wrapper.set_entity_position(char_id, (index, 1))
    return manager, wrapper, dict(wrapper.entities)


@pytest.fixture(autouse=True)
def _clean_module_state():
    """
    Standard-action state is cross-encounter global (`_HELP_GRANTS` holds live
    modifiers on entities, `_DISENGAGED`/`_READIED` are sets/dicts). Drop it around
    every test, exactly as `reset_standard_action_state()` is meant to at combat end,
    so one test's readied action or Help modifier cannot leak into the next.
    """
    sa.reset_standard_action_state()
    yield
    sa.reset_standard_action_state()


@pytest.fixture
def pinned_d20(monkeypatch):
    """
    Pin every die to a constant so a contest is decided purely by the ability gap.

    dnd_engine rolls through the stdlib `random.randint`; patching it makes both the
    attacker's and the defender's d20 identical, so `athletics_bonus > best_of(...)`
    becomes a deterministic, meaningful win/loss.
    """
    def _pin(value=10):
        monkeypatch.setattr(random, "randint", lambda a, b: value)
        return value
    return _pin


# ===========================================================================
# 1. Wiring
# ===========================================================================

class TestRegistration:
    """The one call that was missing — proven by its effects, not by grepping."""

    def test_all_eight_are_registered(self):
        logger.info("🧪 Checking all 8 PHB actions reached ACTION_REGISTRY")
        missing = [a for a in STANDARD_ACTIONS if a not in ACTION_REGISTRY]
        assert not missing, f"register_standard_actions() never ran for: {missing}"
        logger.info("✅ grapple/shove/help/disengage/hide/search/ready/two_weapon_attack registered")

    def test_all_eight_are_offerable(self):
        """
        Offerable = no caller-supplied parameter is missing. This is the trap that
        made four of five Surges unplayable; every standard action must avoid it.
        """
        logger.info("🧪 Checking every standard action is offerable")
        offerable = offerable_actions()
        not_offerable = [a for a in STANDARD_ACTIONS if a not in offerable]
        assert not not_offerable, (
            f"these declare a parameter nothing supplies, so they would be filtered "
            f"out of every menu: {not_offerable}")
        for action in STANDARD_ACTIONS:
            assert is_offerable(action) is True
        logger.info("✅ all 8 are offerable")

    def test_registration_is_idempotent(self):
        logger.info("🧪 Re-running register_standard_actions() must add nothing new")
        added = sa.register_standard_actions()
        assert added == [], f"re-registration rebound live classes: {added}"
        logger.info("✅ idempotent")

    def test_each_resolves_through_the_real_resolver(self, pinned_d20):
        """
        Every action taken through `CombatActionResolver` (the path the game uses)
        with a decisive winner must NOT be refused. A refusal here would mean the menu
        offers something the resolver declines — the failure the filtering suite exists
        to prevent.
        """
        pinned_d20(10)
        logger.info("🧪 Resolving each standard action through CombatActionResolver")
        manager, wrapper, ents = _build([
            ("hero", STRONG, ("Shortsword",)),
            ("foe", FEEBLE, ("Spear",)),
        ])
        wrapper.equip_weapon("hero", "Dagger", slot="OFF_HAND")
        combat_state = {
            "round_number": 1,
            "combatant_states": {
                "hero": {"is_hostile": False, "hp_current": 40, "hp_max": 40,
                         "reaction_available": True},
                "foe": {"is_hostile": True, "hp_current": 40, "hp_max": 40,
                        "reaction_available": True},
            },
        }
        resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                        character_manager=manager,
                                        combat_state=combat_state)
        for action in STANDARD_ACTIONS:
            wrapper.entities["hero"].action_economy.reset_all_costs()
            result = resolver.resolve_action(
                {"actor": "hero", "action_type": action, "target": "foe"})
            assert result.get("refused") is not True, (
                f"{action} was refused by the resolver: {result.get('description')}")
            logger.info(f"   ✅ {action} resolved (success={result.get('success')})")
        logger.info("✅ all 8 resolve through the real resolver")


# ===========================================================================
# 2. Grapple — contested Athletics vs the target's best of Athletics/Acrobatics
# ===========================================================================

class TestGrapple:

    def test_win_applies_grappled(self, pinned_d20):
        pinned_d20(10)
        logger.info("🧪 Grapple WIN: STR20 vs STR3 must apply Grappled")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("foe", FEEBLE, ("Spear",))])
        event = sa.Grapple(source_entity_uuid=ents["hero"].uuid,
                           target_entity_uuid=ents["foe"].uuid).apply()
        assert event.canceled is False
        assert event.contest_won is True
        assert "Grappled" in (ents["foe"].active_conditions or {}), (
            "a won grapple must drop the target's speed to 0 via the Grappled condition")
        logger.info(f"   🤼 {event.attacker_total} vs {event.defender_total} "
                    f"({event.defender_skill}) — Grappled applied")

    def test_loss_changes_nothing(self, pinned_d20):
        pinned_d20(10)
        logger.info("🧪 Grapple LOSS: STR3 vs STR20 must cancel and apply no condition")
        _, _, ents = _build([("weak", FEEBLE, ("Spear",)),
                             ("brute", STRONG, ("Spear",))])
        event = sa.Grapple(source_entity_uuid=ents["weak"].uuid,
                           target_entity_uuid=ents["brute"].uuid).apply()
        assert event.canceled is True, "a lost contest must cancel (success=False)"
        assert event.contest_won is False
        assert "Grappled" not in (ents["brute"].active_conditions or {}), (
            "a lost grapple must leave the target unaffected")
        logger.info(f"   🤼 {event.attacker_total} vs {event.defender_total} — no condition")

    def test_defender_uses_the_higher_of_athletics_or_acrobatics(self):
        """
        RAW: the defender chooses Athletics or Acrobatics. A defender always picks its
        better skill, so a nimble target defends with Acrobatics and a brute with
        Athletics. This is decided by the ability gap, so it holds on any die roll.
        """
        logger.info("🧪 Grapple: defender must pick its stronger contest skill")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("nimble", NIMBLE, ("Spear",)),
                             ("brute", BRUTE, ("Spear",))])
        nimble_event = sa.Grapple(source_entity_uuid=ents["hero"].uuid,
                                  target_entity_uuid=ents["nimble"].uuid).apply()
        assert nimble_event.defender_skill == "acrobatics", (
            "a DEX-20/STR-3 target must defend with Acrobatics")
        brute_event = sa.Grapple(source_entity_uuid=ents["hero"].uuid,
                                 target_entity_uuid=ents["brute"].uuid).apply()
        assert brute_event.defender_skill == "athletics", (
            "a STR-20/DEX-3 target must defend with Athletics")
        logger.info("   🤼 acrobatics for the nimble target, athletics for the brute")

    def test_missing_target_is_refused_not_crashed(self):
        logger.info("🧪 Grapple with no target must cancel cleanly")
        _, _, ents = _build([("hero", STRONG, ("Spear",))])
        event = sa.Grapple(source_entity_uuid=ents["hero"].uuid,
                           target_entity_uuid=None).apply()
        assert event.canceled is True
        # No roll happened, so the contest fields stay unset — the marker that
        # separates a gate rejection from a genuine lost contest.
        assert getattr(event, "attacker_total", None) is None
        logger.info("   ✅ cancelled without a contest")


# ===========================================================================
# 3. Shove — same contest; prone by default, push on request
# ===========================================================================

class TestShove:

    def test_win_knocks_prone(self, pinned_d20):
        pinned_d20(10)
        logger.info("🧪 Shove WIN (default mode) must apply Prone")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("foe", FEEBLE, ("Spear",))])
        event = sa.Shove(source_entity_uuid=ents["hero"].uuid,
                         target_entity_uuid=ents["foe"].uuid).apply()
        assert event.canceled is False and event.contest_won is True
        assert "Prone" in (ents["foe"].active_conditions or {})
        logger.info("   🫱 target knocked prone")

    def test_loss_changes_nothing(self, pinned_d20):
        pinned_d20(10)
        logger.info("🧪 Shove LOSS must cancel and leave no Prone")
        _, _, ents = _build([("weak", FEEBLE, ("Spear",)),
                             ("brute", STRONG, ("Spear",))])
        event = sa.Shove(source_entity_uuid=ents["weak"].uuid,
                         target_entity_uuid=ents["brute"].uuid).apply()
        assert event.canceled is True and event.contest_won is False
        assert "Prone" not in (ents["brute"].active_conditions or {})
        logger.info("   🫱 no Prone on a lost shove")

    def test_push_mode_does_not_apply_prone(self, pinned_d20):
        """
        `shove_mode="push"` reports the 5-ft push intent (the grid owns the actual
        move) and must NOT knock the target prone — the two halves are exclusive.
        """
        pinned_d20(10)
        logger.info("🧪 Shove push mode must report a push, not Prone")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("foe", FEEBLE, ("Spear",))])
        action = sa.Shove(source_entity_uuid=ents["hero"].uuid,
                          target_entity_uuid=ents["foe"].uuid)
        action.shove_mode = "push"
        event = action.apply()
        assert event.canceled is False and event.contest_won is True
        assert "Prone" not in (ents["foe"].active_conditions or {})
        assert "5 feet" in event.status_message
        logger.info("   🫱 push reported, no Prone applied")


# ===========================================================================
# 4. Help — measurable advantage on the ally's NEXT attack, then expires
# ===========================================================================

class TestHelp:

    def test_help_records_and_expires_the_grant(self):
        logger.info("🧪 Help must record an advantage grant and be able to expire it")
        _, _, ents = _build([("helper", STRONG, ("Spear",)),
                             ("ally", STRONG, ("Spear",))])
        assert sa.has_help(ents["ally"].uuid) is False
        event = sa.Help(source_entity_uuid=ents["helper"].uuid,
                        target_entity_uuid=ents["ally"].uuid).apply()
        assert event.canceled is False
        assert sa.has_help(ents["ally"].uuid) is True
        assert sa.expire_help(ents["ally"].uuid) is True
        assert sa.has_help(ents["ally"].uuid) is False
        logger.info("   🤝 grant recorded then expired")

    def test_re_helping_does_not_stack(self):
        """5e advantage does not stack, and two unremoved modifiers would leak one."""
        logger.info("🧪 Help twice must leave exactly one grant")
        _, _, ents = _build([("helper", STRONG, ("Spear",)),
                             ("ally", STRONG, ("Spear",))])
        ally = ents["ally"]
        sa.Help(source_entity_uuid=ents["helper"].uuid,
                target_entity_uuid=ally.uuid).apply()
        before = len(ally.equipment.attack_bonus.self_static.advantage_modifiers)
        sa.Help(source_entity_uuid=ents["helper"].uuid,
                target_entity_uuid=ally.uuid).apply()
        after = len(ally.equipment.attack_bonus.self_static.advantage_modifiers)
        assert after == before, "re-helping stacked a second advantage modifier"
        logger.info("   🤝 no stacking")

    def test_help_measurably_raises_the_allys_hit_rate(self):
        """
        The point of Help is a real mechanical edge. Over many attacks against the
        same AC, the helped hit-rate must clearly beat the unhelped one — which only
        holds because the advantage patch rolls two dice and keeps the higher.
        """
        logger.info("🧪 Help must MEASURABLY raise the ally's hit rate (advantage)")
        trials = 400

        def hit_rate(with_help):
            random.seed(20260911)
            # A high-AC dummy keeps the base hit-rate mid-range; a low-AC target is
            # already hit ~95% of the time, leaving advantage no room to show.
            _, _, ents = _build(
                [("helper", STRONG, ("Spear",)),
                 ("ally", STRONG, ("Spear",)),
                 ("dummy", FEEBLE, ("Spear",))],
                overrides={"dummy": {"armor_class": 22}})
            ally, dummy = ents["ally"], ents["dummy"]
            hits = 0
            for _ in range(trials):
                if with_help:
                    sa.Help(source_entity_uuid=ents["helper"].uuid,
                            target_entity_uuid=ally.uuid).apply()
                ally.action_economy.reset_all_costs()
                event = Attack(source_entity_uuid=ally.uuid,
                               target_entity_uuid=dummy.uuid,
                               weapon_slot=WeaponSlot.MAIN_HAND).apply()
                outcome = getattr(event, "attack_outcome", None) if event else None
                if outcome in (AttackOutcome.HIT, AttackOutcome.CRIT):
                    hits += 1
                sa.expire_help(ally.uuid)   # advantage is for the NEXT attack only
            return hits / trials

        helped = hit_rate(True)
        plain = hit_rate(False)
        logger.info(f"   🤝 helped hit-rate {helped:.2%} vs plain {plain:.2%} "
                    f"(+{(helped - plain) * 100:.1f}pp)")
        assert helped > plain + 0.08, (
            f"Help gave no measurable advantage: {helped:.2%} vs {plain:.2%} — "
            f"advantage is decorative if _roll_with_advantage rolls one die")


# ===========================================================================
# 5. Disengage — suppresses a REAL opportunity attack
# ===========================================================================

class TestDisengage:

    def _grid_setup(self):
        manager, wrapper, ents = _build([("runner", STRONG, ("Spear",)),
                                        ("guard", STRONG, ("Spear",))])
        wrapper.set_entity_position("runner", (1, 1))
        wrapper.set_entity_position("guard", (2, 1))   # adjacent
        grid = TacticalGrid(BattleMap(name="t", rows=["......"] * 3), dnd_wrapper=wrapper)
        combat_state = {
            "round_number": 1,
            "combatant_states": {
                "runner": {"is_hostile": False, "reaction_available": True,
                           "hp_current": 40, "hp_max": 40},
                "guard": {"is_hostile": True, "reaction_available": True,
                          "hp_current": 40, "hp_max": 40},
            },
        }
        return wrapper, ents, TacticalRules(grid, wrapper, combat_state), combat_state

    def test_disengage_removes_the_provoked_attacker(self):
        logger.info("🧪 Disengage must suppress a real opportunity attack")
        wrapper, ents, rules, _ = self._grid_setup()
        flee_to = (5, 1)   # out of the guard's reach
        before = rules.opportunity_attackers("runner", flee_to)
        assert "guard" in before, (
            "the guard should provoke on a runner leaving its reach — setup is wrong")
        logger.info(f"   🏃 before Disengage: provoked = {before}")

        event = sa.Disengage(source_entity_uuid=ents["runner"].uuid).apply()
        assert event.canceled is False
        assert sa.is_disengaged(ents["runner"].uuid) is True

        after = rules.opportunity_attackers("runner", flee_to)
        assert after == [], f"Disengage did not suppress the opportunity attack: {after}"
        logger.info("   🏃 after Disengage: no attackers provoked")

    def test_disengage_lapses_on_reset(self):
        """5e: Disengage lasts 'for the rest of your turn'. `reset_reactions()` (once
        per round) must clear it, or one Disengage is permanent immunity."""
        logger.info("🧪 Disengage must lapse when reactions reset")
        wrapper, ents, rules, _ = self._grid_setup()
        sa.Disengage(source_entity_uuid=ents["runner"].uuid).apply()
        assert sa.is_disengaged(ents["runner"].uuid) is True
        rules.reset_reactions()
        assert sa.is_disengaged(ents["runner"].uuid) is False
        assert rules.opportunity_attackers("runner", (5, 1)) == ["guard"]
        logger.info("   🏃 disengage cleared; opportunity attack returns")


# ===========================================================================
# 6. Hide — Stealth vs the observers' passive Perception
# ===========================================================================

class TestHide:

    def test_unobserved_hide_succeeds(self):
        logger.info("🧪 Hide with nobody watching must succeed (Invisible applied)")
        _, _, ents = _build([("scout", NIMBLE, ("Spear",))])
        event = sa.Hide(source_entity_uuid=ents["scout"].uuid).apply()
        assert event.canceled is False and event.hidden is True
        assert "Invisible" in (ents["scout"].active_conditions or {})
        logger.info("   👁️  hidden while unobserved")

    def test_hide_fails_against_a_sharp_observer(self, pinned_d20):
        """
        Pin the d20 low so the DEX-20 scout's Stealth cannot beat a WIS-20 proficient
        watcher's passive Perception — hiding in the open in front of a sentry fails.
        """
        pinned_d20(1)
        logger.info("🧪 Hide must fail when a sharp observer beats the Stealth roll")
        _, _, ents = _build([("scout", NIMBLE, ("Spear",)),
                             ("watcher", HAWKEYE, ("Spear",))])
        event = sa.Hide(source_entity_uuid=ents["scout"].uuid,
                        observer_uuids=[ents["watcher"].uuid]).apply()
        assert event.canceled is True and event.hidden is False, (
            f"Stealth {event.stealth_total} should have lost to passive Perception "
            f"{event.best_passive_perception}")
        assert "Invisible" not in (ents["scout"].active_conditions or {})
        logger.info(f"   👁️  Stealth {event.stealth_total} < passive "
                    f"{event.best_passive_perception}: not hidden")


# ===========================================================================
# 7. Search — the counter to Hide
# ===========================================================================

class TestSearch:

    def test_search_finds_and_reveals_a_hidden_creature(self, pinned_d20):
        pinned_d20(20)   # a max Perception roll beats the hider's passive Stealth
        logger.info("🧪 Search must reveal a hidden creature (remove Invisible)")
        _, _, ents = _build([("scout", FEEBLE, ("Spear",)),
                             ("seeker", HAWKEYE, ("Spear",))])
        # First hide the scout unobserved so it actually carries Invisible.
        sa.Hide(source_entity_uuid=ents["scout"].uuid).apply()
        assert "Invisible" in (ents["scout"].active_conditions or {})

        event = sa.Search(source_entity_uuid=ents["seeker"].uuid,
                          target_entity_uuid=ents["scout"].uuid).apply()
        assert event.canceled is False and event.found is True
        assert "Invisible" not in (ents["scout"].active_conditions or {}), (
            "a successful Search must strip the hider's Invisible")
        logger.info(f"   🔍 Perception {event.perception_total} ≥ DC {event.dc}: found")

    def test_search_fails_against_a_better_hider(self, pinned_d20):
        pinned_d20(1)    # a min Perception roll loses to the hider's passive Stealth
        logger.info("🧪 Search must fail when the hider's Stealth wins")
        _, _, ents = _build([("scout", NIMBLE, ("Spear",)),
                             ("seeker", FEEBLE, ("Spear",))])
        sa.Hide(source_entity_uuid=ents["scout"].uuid).apply()
        event = sa.Search(source_entity_uuid=ents["seeker"].uuid,
                          target_entity_uuid=ents["scout"].uuid).apply()
        assert event.canceled is True and event.found is False
        assert "Invisible" in (ents["scout"].active_conditions or {}), (
            "a failed Search must leave the hider hidden")
        logger.info(f"   🔍 Perception {event.perception_total} < DC {event.dc}: nothing found")


# ===========================================================================
# 8. Ready — store the declared intent; the reaction is spent later
# ===========================================================================

class TestReady:

    def test_ready_stores_the_declared_action(self):
        logger.info("🧪 Ready must store a trigger + action and not spend the reaction")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("foe", FEEBLE, ("Spear",))])
        event = sa.Ready(source_entity_uuid=ents["hero"].uuid,
                         target_entity_uuid=ents["foe"].uuid,
                         trigger="the door opens", readied_action="attack").apply()
        assert event.canceled is False
        stored = sa.readied_action(ents["hero"].uuid)
        assert stored is not None
        assert stored["trigger"] == "the door opens"
        assert stored["action"] == "attack"
        assert stored["target"] == ents["foe"].uuid
        logger.info(f"   ⏳ readied: {stored['action']} on '{stored['trigger']}'")

    def test_consume_readied_takes_it_off_the_shelf(self):
        logger.info("🧪 consume_readied_action must return then clear the stored intent")
        _, _, ents = _build([("hero", STRONG, ("Spear",))])
        sa.Ready(source_entity_uuid=ents["hero"].uuid).apply()
        assert sa.consume_readied_action(ents["hero"].uuid) is not None
        assert sa.readied_action(ents["hero"].uuid) is None
        logger.info("   ⏳ consumed once, gone afterwards")


# ===========================================================================
# 9. Two-Weapon fighting — bonus action, light off-hand only
# ===========================================================================

class TestTwoWeaponFighting:

    def test_needs_an_off_hand_weapon(self):
        logger.info("🧪 Two-weapon must be refused with no off-hand weapon")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("foe", FEEBLE, ("Spear",))])
        event = sa.TwoWeaponAttack(source_entity_uuid=ents["hero"].uuid,
                                   target_entity_uuid=ents["foe"].uuid).apply()
        assert event.canceled is True
        assert "off-hand" in event.status_message
        logger.info("   ⚔️  refused: no off-hand weapon")

    def test_rejects_a_non_light_off_hand_weapon(self):
        logger.info("🧪 Two-weapon must reject a non-light off-hand weapon")
        _, wrapper, ents = _build([("hero", STRONG, ("Shortsword",)),
                                   ("foe", FEEBLE, ("Spear",))])
        # A longsword is not light; two-weapon fighting must reject it.
        wrapper.equip_weapon("hero", "Longsword", slot="OFF_HAND")
        event = sa.TwoWeaponAttack(source_entity_uuid=ents["hero"].uuid,
                                   target_entity_uuid=ents["foe"].uuid).apply()
        assert event.canceled is True
        assert "light" in event.status_message
        logger.info("   ⚔️  refused: off-hand weapon is not light")

    def test_light_off_hand_swings_and_spends_only_the_bonus_action(self):
        """
        A legal off-hand swing must cost a BONUS action and leave the main action
        intact — the loan/reclaim dance in the action exists precisely so the nested
        engine `Attack` does not eat the real action.
        """
        logger.info("🧪 Two-weapon with a light off-hand must spend bonus, keep action")
        _, wrapper, ents = _build([("hero", STRONG, ("Shortsword",)),
                                   ("foe", FEEBLE, ("Spear",))])
        wrapper.equip_weapon("hero", "Dagger", slot="OFF_HAND")
        hero = ents["hero"]
        actions_before = hero.action_economy.actions.normalized_score
        bonus_before = hero.action_economy.bonus_actions.normalized_score
        assert bonus_before == 1

        event = sa.TwoWeaponAttack(source_entity_uuid=hero.uuid,
                                   target_entity_uuid=ents["foe"].uuid).apply()
        assert event.canceled is False, event.status_message

        assert hero.action_economy.bonus_actions.normalized_score == bonus_before - 1, (
            "the off-hand swing must consume the bonus action")
        assert hero.action_economy.actions.normalized_score == actions_before, (
            "two-weapon fighting must NOT consume the main action")
        logger.info(f"   ⚔️  actions {actions_before}->"
                    f"{hero.action_economy.actions.normalized_score}, "
                    f"bonus {bonus_before}->"
                    f"{hero.action_economy.bonus_actions.normalized_score}")

    def test_is_light_weapon_matches_by_name(self):
        logger.info("🧪 is_light_weapon must match light weapons by name substring")
        assert sa.is_light_weapon("Kaladin's handaxe") is True
        assert sa.is_light_weapon("Dagger") is True
        assert sa.is_light_weapon("Longsword") is False
        assert sa.is_light_weapon("") is False
        logger.info("   ⚔️  light-weapon detection correct")


# ===========================================================================
# 10. Cross-encounter state cleanup
# ===========================================================================

class TestStateCleanup:

    def test_reset_clears_help_disengage_and_ready(self):
        """
        Every bit of this module's global state must drop at combat end, or a decision
        from a fight three scenes ago leaks into the next one — the same class of bug
        as a leaked wall between test files.
        """
        logger.info("🧪 reset_standard_action_state must clear all module state")
        _, _, ents = _build([("hero", STRONG, ("Spear",)),
                             ("ally", STRONG, ("Spear",))])
        sa.Help(source_entity_uuid=ents["hero"].uuid,
                target_entity_uuid=ents["ally"].uuid).apply()
        sa.Disengage(source_entity_uuid=ents["hero"].uuid).apply()
        sa.Ready(source_entity_uuid=ents["hero"].uuid).apply()
        assert sa.has_help(ents["ally"].uuid)
        assert sa.is_disengaged(ents["hero"].uuid)
        assert sa.readied_action(ents["hero"].uuid) is not None

        sa.reset_standard_action_state()

        assert sa.has_help(ents["ally"].uuid) is False
        assert sa.is_disengaged(ents["hero"].uuid) is False
        assert sa.readied_action(ents["hero"].uuid) is None
        logger.info("   🧹 help, disengage and ready all cleared")
