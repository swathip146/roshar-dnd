"""
The action menu must be filtered PER ACTOR, not just per action.

`is_offerable()` (tests/combat/test_only_usable_actions_are_offered.py) answers an
actor-INDEPENDENT question: can the resolver supply this action's parameters? It
correctly says yes to all four Surges. Used alone as a menu, that is a trap — and it
was being used alone as a menu, in both consumers.

MEASURED BEFORE THIS FIX. The NPC menu built for a plain goblin (no radiant_order,
surgebinding_level=0, stormlight_current=0) was:

    ['attack', 'dash', 'dodge', 'lashing', 'progression_healing',
     'illumination', 'soulcast']

Four of seven entries — 57% of the menu — were unresolvable. Each surge's own
`_validate` in roshar_actions.py cancels for "not Windrunner/Skybreaker",
"Insufficient Surgebinding level" or "Insufficient Stormlight". Confirmed by
resolving them: all four returned success=False.

This is the SAME harm `is_offerable` was written to stop, reintroduced one layer
down: 15 of 28 NPC actions in one live encounter went to actions the resolver
refused, each burning a real LLM call while the actor kept its action economy, so the
turn loop spun until the stall-breaker forced it along.

ROOT CAUSE. `CombatSessionManager._character_meets_requirements` had the Radiant
Order check, but *after* an early `if not requires: return True` — and `requires` is
None for all four Surges, so that block was unreachable dead code. Stormlight and
`min_surgebinding_level` were never checked in any code path. Both menu builders
(`_get_available_actions` for the player, `_build_npc_context` for the NPC AI) called
that method, so both were unfiltered.

The tests here assert on the OUTCOME the game cares about: everything a menu offers
an actor must actually resolve for that actor.
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
                                               is_usable_by, offerable_actions,
                                               unusable_reason, usable_actions)
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.combat_session_manager import CombatSessionManager
from components.dnd_engine_wrapper import DnDEngineWrapper

ALL_SURGES = ("lashing", "progression_healing", "illumination", "soulcast")

# The three actions any combatant can always take. Until standard_actions.py was
# wired into ACTION_REGISTRY (handoff item 5) these were the WHOLE menu for a
# non-Radiant, so several tests below asserted exact equality with this set. They now
# co-exist with the eight universal PHB actions, so those tests assert the real INTENT
# instead — the mundane baseline is present and NO surge leaks in.
MUNDANE_ACTIONS = {"attack", "dash", "dodge"}

# The PHB actions from components/combat/standard_actions.py. They are UNIVERSAL (any
# creature may attempt them) and their per-action OUTCOME — a lost Grapple/Shove
# contest, an empty Search, an absent off-hand weapon for two-weapon fighting — is a
# valid result, exercised exhaustively in tests/combat/test_standard_actions.py. That
# is a different thing from the surge-trap this file guards against (offering a goblin
# a Lashing its own _validate can only cancel), so `_resolve_each` skips them: a random
# contest loss must not read as a menu bug.
STANDARD_ACTIONS = ("grapple", "shove", "help", "disengage", "hide", "search",
                    "ready", "two_weapon_attack")

# Who is in every fixture combat, and what they are.
CAST = {
    # A plain monster: the actor that was being offered four Surges.
    "goblin": {},
    "windrunner": {"radiant_order": "Windrunner"},
    "lightweaver": {"radiant_order": "Lightweaver"},
    "edgedancer": {"radiant_order": "Edgedancer"},
}


def _sheet(char_id, radiant_order=None, **over):
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 14, "charisma": 12},
        "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
        "armor_class": 14, "character_class": "Fighter", "race": "Alethi",
        "background": "Soldier", "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    if radiant_order:
        # Capacity matters: CharacterManager clamps stormlight_current to
        # stormlight_capacity, so setting current alone silently yields 0.
        # Investiture Points fund the COSTED arts (Regrowth = 2 IP); cantrips are
        # free and never touch this pool. Both are set so a Radiant can both cast
        # a free cantrip and pay for a costed art. (No migration fires because
        # stormlight_capacity > 0.)
        sheet.update({"radiant_order": radiant_order, "surgebinding_level": 3,
                      "stormlight_capacity": 10, "stormlight_current": 10,
                      "investiture_points": {"current": 10, "maximum": 10}})
    sheet.update(over)
    return sheet


class _Engine:
    def __init__(self, character_manager):
        self.character_manager = character_manager
        self.game_state = type("S", (), {"characters": {}})()

    def update_combat_state(self, *a, **k):
        return None


@pytest.fixture
def table():
    """
    One goblin, three Radiants of different Orders, all adjacent to the goblin.

    Adjacency is load-bearing: `attack` is on every menu, and a Radiant two squares
    away fails it for reach — which would look like a menu bug in the
    everything-offered-resolves test.
    """
    manager = CharacterManager()
    for char_id, extra in CAST.items():
        manager.add_character(_sheet(char_id, **extra))

    engine = _Engine(manager)
    wrapper = DnDEngineWrapper(game_engine=engine, character_manager=manager)

    # Goblin in the middle, every Radiant within reach of it.
    wrapper.set_entity_position("goblin", (1, 1))
    wrapper.set_entity_position("windrunner", (0, 1))
    wrapper.set_entity_position("lightweaver", (1, 0))
    wrapper.set_entity_position("edgedancer", (2, 1))

    ids = list(CAST)
    combat_state = {
        "round_number": 1, "current_turn_index": 0, "combat_log": [],
        "initiative_order": [{"char_id": c, "initiative": 20 - i}
                             for i, c in enumerate(ids)],
        "active_combatants": ids,
        "combatant_states": {
            c: {"is_hostile": c == "goblin", "hp_current": 40, "hp_max": 40,
                "actions_remaining": 1, "bonus_actions_remaining": 1,
                "reaction_available": True}
            for c in ids},
    }
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=manager,
                                    combat_state=combat_state)
    session = CombatSessionManager(
        combat_state=combat_state, game_engine=engine,
        character_manager=manager, dnd_engine_wrapper=wrapper,
        combat_action_resolver=resolver, combat_narrative_generator=None,
        npc_ai_agent=None, input_provider=lambda prompt="": "1")
    return session, resolver, wrapper, manager


def _npc_menu(session, char_id):
    return session._build_npc_context(char_id)["available_actions"]


def _player_menu(session, char_id):
    categories = session._get_available_actions(char_id)
    return sorted({item["action_type"]
                   for category in categories.values()
                   for item in (category.get("actions") or [])})


# ---------------------------------------------------------------------------
# 1. The registry knows what each actor can do
# ---------------------------------------------------------------------------

class TestUsableActionsGatesOnActorState:
    """
    `usable_actions(actor_state)` is the single per-actor filter. It reads
    `radiant_order`, `surgebinding_level` and `stormlight_current` off anything
    attribute- or key-addressable (CharacterData, the Entity mirror, or a dict).
    """

    GOBLIN = {"radiant_order": None, "surgebinding_level": 0,
              "stormlight_current": 0}
    WINDRUNNER = {"radiant_order": "Windrunner", "surgebinding_level": 3,
                  "stormlight_current": 10}

    @pytest.mark.parametrize("surge", ALL_SURGES)
    def test_a_goblin_gets_no_surges(self, surge):
        """It has no Order at all, so every surge is refused by its `_validate`."""
        assert is_usable_by(surge, self.GOBLIN) is False
        assert "Radiant Order" in unusable_reason(surge, self.GOBLIN)

    def test_a_goblin_still_gets_the_mundane_actions(self):
        """Filtering must not empty the menu — a goblin must still be able to hit."""
        usable = set(usable_actions(self.GOBLIN))
        assert MUNDANE_ACTIONS <= usable, usable        # can still fight
        assert not (set(ALL_SURGES) & usable), usable   # but no surges

    def test_a_windrunner_gets_lashing_and_not_the_others(self):
        usable = set(usable_actions(self.WINDRUNNER))
        assert "lashing" in usable
        assert not ({"illumination", "soulcast", "progression_healing"} & usable), (
            "a Windrunner has Adhesion and Gravitation, not Illumination, "
            "Transformation or Progression")

    @pytest.mark.parametrize("order,surge", [
        ("Windrunner", "lashing"),
        ("Skybreaker", "lashing"),
        ("Edgedancer", "progression_healing"),
        ("Truthwatcher", "progression_healing"),
        ("Lightweaver", "illumination"),
        ("Elsecaller", "soulcast"),
    ])
    def test_each_order_gets_its_own_surge(self, order, surge):
        # Investiture Points are supplied so a COSTED art (progression_healing =
        # Regrowth, 2 IP) is affordable; free cantrips ignore the pool.
        actor = {"radiant_order": order, "surgebinding_level": 3,
                 "stormlight_current": 10,
                 "investiture_points": {"current": 10, "maximum": 10}}
        assert is_usable_by(surge, actor) is True, unusable_reason(surge, actor)

    def test_the_goblin_and_the_windrunner_get_different_menus(self):
        """The whole point, stated as one assertion."""
        assert set(usable_actions(self.GOBLIN)) != set(
            usable_actions(self.WINDRUNNER))

    def test_surgebinding_level_is_enforced(self):
        """
        `min_surgebinding_level` was checked NOWHERE before this fix — not in the
        menu, only inside the action's own `_validate`. Soulcast needs 2.
        """
        novice = {"radiant_order": "Lightweaver", "surgebinding_level": 1,
                  "stormlight_current": 10}
        assert is_usable_by("illumination", novice) is True   # needs 1
        assert is_usable_by("soulcast", novice) is False      # needs 2
        assert "Surgebinding level 2" in unusable_reason("soulcast", novice)

    def test_investiture_is_enforced_per_art_cost(self):
        """
        The NEW economy (plan 2.9): cantrips are FREE and costed Invested Arts are
        paid in Investiture Points via cosmere_rules.investiture_cost(). Regrowth
        (progression_healing) is a 1st-level art = 2 IP, so a Radiant one point
        short cannot cast it while a free cantrip stays available.

        (The old model charged 1/1/2/3 Stormlight spheres for Lashing/Illumination/
        Progression/Soulcast; those cantrips are now free — see
        AUDIT_HARDCODED_SURGE_ACCURACY.md §3.)
        """
        # A free cantrip is available regardless of the resource pool.
        rich = {"radiant_order": "Lightweaver", "surgebinding_level": 3,
                "stormlight_current": 0,
                "investiture_points": {"current": 0, "maximum": 0}}
        assert is_usable_by("illumination", rich) is True    # free cantrip

        # A costed art is gated exactly at its IP cost.
        one_ip = {"radiant_order": "Edgedancer", "surgebinding_level": 3,
                  "stormlight_current": 10,
                  "investiture_points": {"current": 1, "maximum": 10}}
        assert is_usable_by("progression_healing", one_ip) is False   # needs 2
        assert "2 Investiture Points" in unusable_reason("progression_healing", one_ip)

        two_ip = dict(one_ip, investiture_points={"current": 2, "maximum": 10})
        assert is_usable_by("progression_healing", two_ip) is True

    def test_a_drained_radiant_keeps_free_cantrips_but_loses_costed_arts(self):
        """
        Retargeted for the IP economy: draining a Radiant no longer removes its
        FREE cantrips (a cantrip costs nothing), but an empty Investiture pool does
        remove its COSTED arts. Both halves matter — over-filtering a free cantrip
        would be as wrong as offering an unpayable art.
        """
        # Windrunner, fully drained: Lashing is a free cantrip and must remain.
        drained_wr = {"radiant_order": "Windrunner", "surgebinding_level": 3,
                      "stormlight_current": 0,
                      "investiture_points": {"current": 0, "maximum": 0}}
        usable = set(usable_actions(drained_wr))
        assert MUNDANE_ACTIONS <= usable
        assert "lashing" in usable, "a free cantrip must survive being drained"

        # Edgedancer with an empty IP pool: the costed Regrowth art is gated out.
        drained_ed = {"radiant_order": "Edgedancer", "surgebinding_level": 3,
                      "stormlight_current": 10,
                      "investiture_points": {"current": 0, "maximum": 10}}
        assert "progression_healing" not in set(usable_actions(drained_ed))
        assert "Investiture" in unusable_reason("progression_healing", drained_ed)

    def test_shardblade_needs_a_summoned_blade(self):
        """
        `requires: shardblade_summoned` was the ONE gate the old code reached, and
        it must keep working now that the branch order changed.
        """
        unarmed = {"radiant_order": "Windrunner", "surgebinding_level": 3,
                   "stormlight_current": 10}
        assert is_usable_by("shardblade_attack", unarmed) is False
        armed = dict(unarmed, shardblade_summoned=True)
        assert is_usable_by("shardblade_attack", armed) is True

    def test_move_is_still_excluded_for_everyone(self):
        """Per-actor filtering must not undo the parameter filter."""
        for actor in (self.GOBLIN, self.WINDRUNNER):
            assert "move" not in usable_actions(actor)

    def test_an_unknown_action_is_usable_by_nobody(self):
        assert is_usable_by("teleport_to_shadesmar", self.WINDRUNNER) is False

    def test_usable_is_a_subset_of_offerable(self):
        """
        Per-actor filtering only ever REMOVES. If it added anything, it would be
        offering an action whose parameters nothing supplies.
        """
        for actor in (self.GOBLIN, self.WINDRUNNER):
            assert set(usable_actions(actor)) <= set(offerable_actions())

    def test_missing_state_denies_rather_than_allows(self):
        """
        The old bug in miniature: the action classes guard with `hasattr` and SKIP
        the check when the attribute is absent, so absent state read as permission.
        An actor with no Roshar state at all must get no surges.
        """
        for actor in ({}, None):
            usable = set(usable_actions(actor))
            assert MUNDANE_ACTIONS <= usable
            assert not (set(ALL_SURGES) & usable), usable


# ---------------------------------------------------------------------------
# 2. Both consumers apply it
# ---------------------------------------------------------------------------

class TestBothMenuBuildersFilterPerActor:
    """
    A helper nobody calls is the failure mode that hid six subsystems in this
    project. These assert the filter is APPLIED, through the real session manager.
    """

    def test_the_npc_menu_for_a_goblin_has_no_surges(self, table):
        """
        THE REGRESSION, exactly as measured: this list used to be
        ['attack', 'dash', 'dodge', 'lashing', 'progression_healing',
         'illumination', 'soulcast'].
        """
        session, *_ = table
        offered = _npc_menu(session, "goblin")
        surges = [a for a in offered if a in ALL_SURGES]
        assert not surges, (
            f"the NPC AI is told a goblin can {surges}; every such choice is "
            f"cancelled by the surge's own _validate, wasting a real LLM call "
            f"and leaving the actor's action economy untouched")

    def test_the_player_menu_for_a_goblin_has_no_surges(self, table):
        session, *_ = table
        offered = _player_menu(session, "goblin")
        assert not [a for a in offered if a in ALL_SURGES], offered

    def test_the_npc_menu_offers_the_right_surge_to_each_order(self, table):
        session, *_ = table
        assert "lashing" in _npc_menu(session, "windrunner")
        assert "illumination" in _npc_menu(session, "lightweaver")
        assert "progression_healing" in _npc_menu(session, "edgedancer")

    def test_the_player_menu_offers_the_right_surge_to_each_order(self, table):
        session, *_ = table
        assert "lashing" in _player_menu(session, "windrunner")
        assert "illumination" in _player_menu(session, "lightweaver")
        assert "progression_healing" in _player_menu(session, "edgedancer")

    def test_a_windrunner_is_not_offered_another_orders_surge(self, table):
        """
        The player-side half of the bug: a Windrunner was offered Soulcast, which
        their Order cannot use, with no way to know before losing the turn.
        """
        session, *_ = table
        for menu in (_npc_menu(session, "windrunner"),
                     _player_menu(session, "windrunner")):
            assert "soulcast" not in menu
            assert "illumination" not in menu
            assert "progression_healing" not in menu

    def test_the_goblin_and_the_windrunner_get_different_npc_menus(self, table):
        session, *_ = table
        assert set(_npc_menu(session, "goblin")) != set(
            _npc_menu(session, "windrunner"))

    def test_draining_investiture_removes_the_costed_art_from_the_menu(self, table):
        """
        Live state, retargeted for the IP economy. Draining the Edgedancer's
        Investiture Points removes the COSTED Regrowth art from both menus, while a
        Windrunner's FREE Lashing cantrip survives having no Stormlight at all.
        """
        session, _, wrapper, manager = table
        assert "progression_healing" in _npc_menu(session, "edgedancer")

        manager.characters["edgedancer"].investiture_points["current"] = 0
        assert "progression_healing" not in _npc_menu(session, "edgedancer"), (
            "an Edgedancer with no Investiture is still offered a costed art")
        assert "progression_healing" not in _player_menu(session, "edgedancer")

        # A free cantrip must NOT be removed for lack of Stormlight.
        assert wrapper.set_roshar_attr("windrunner", "stormlight_current", 0)
        assert "lashing" in _npc_menu(session, "windrunner")
        assert "lashing" in _player_menu(session, "windrunner")

    def test_partial_investiture_gates_the_costed_art(self, table):
        """One IP short of Regrowth's 2-point cost: it leaves the menu; at 2 it returns."""
        session, _, _, manager = table
        manager.characters["edgedancer"].investiture_points["current"] = 1
        assert "progression_healing" not in _npc_menu(session, "edgedancer")

        manager.characters["edgedancer"].investiture_points["current"] = 2
        assert "progression_healing" in _npc_menu(session, "edgedancer")

    @pytest.mark.parametrize("char_id", sorted(CAST))
    def test_no_menu_is_ever_empty(self, table, char_id):
        """Both directions: over-filtering leaves an actor able only to stall."""
        session, *_ = table
        assert _npc_menu(session, char_id), f"{char_id} has no NPC actions"
        assert _player_menu(session, char_id), f"{char_id} has no player actions"

    @pytest.mark.parametrize("char_id", sorted(CAST))
    def test_attack_survives_the_filter_for_everyone(self, table, char_id):
        session, *_ = table
        assert "attack" in _npc_menu(session, char_id)
        assert "attack" in _player_menu(session, char_id)


# ---------------------------------------------------------------------------
# 3. The invariant that matters: offered => resolves
# ---------------------------------------------------------------------------

class TestEverythingOfferedActuallyResolves:
    """
    The outcome assertion. A menu is only correct if every entry on it succeeds
    through `CombatActionResolver` — the path the game actually uses. Both earlier
    filters were added because an offered-but-refused action is worse than a missing
    one: the actor keeps its economy and the turn loop spins.
    """

    @staticmethod
    def _resolve_each(session, resolver, wrapper, actor, menu):
        """
        Resolve every menu entry from a fresh action economy; collect refusals.

        "Refused" is the thing being tested, and it is NOT the same as
        `success=False`. For an attack the resolver deliberately reports
        `success=hit`, so a legal swing that rolls a miss comes back False —
        that action WAS taken and the economy WAS consumed, which is exactly the
        healthy case. The failure this file exists to catch is the action being
        declined: `refused=True` (no economy, or the engine said no) or a cancelled
        event (a gate in `_validate` rejected the actor).
        """
        target = "goblin" if actor != "goblin" else "windrunner"
        refusals = []
        for action_type in menu:
            # A universal PHB action that fails a die roll (a lost Grapple/Shove
            # contest, an empty Search) or an unmet per-action prerequisite (no
            # off-hand weapon for two-weapon fighting) cancels its event — which is a
            # valid OUTCOME, not the surge-trap this file exists to catch, and is
            # verified in tests/combat/test_standard_actions.py. Skipping keeps this
            # invariant focused on "no actor is offered a Surge it can never resolve".
            if action_type in STANDARD_ACTIONS:
                continue
            # Activated class features (Rage/Second Wind/Action Surge) are offered to
            # any actor that owns them — and the fixtures build these actors as level-5
            # Fighters, so Second Wind/Action Surge legitimately appear. Their
            # resolution is exhaustively verified in test_activated_class_features.py;
            # this invariant guards against surge-traps, not class features, so skip
            # them the same way as the PHB actions above.
            if resolver.ACTION_REGISTRY.get(action_type, {}).get("type") == "class_feature":
                continue
            wrapper.entities[actor].action_economy.reset_all_costs()
            result = resolver.resolve_action({"actor": actor,
                                              "action_type": action_type,
                                              "target": target})
            event = result.get("event")
            declined = (result.get("refused") is True
                        or event is None
                        or getattr(event, "canceled", False))
            if declined:
                refusals.append(
                    (action_type,
                     result.get("error") or result.get("description")
                     or getattr(event, "status_message", None)))
        return refusals

    @pytest.mark.parametrize("actor", sorted(CAST))
    def test_every_npc_menu_entry_resolves(self, table, actor):
        session, resolver, wrapper, manager = table
        # Give healing something to do, so progression_healing is not a no-op.
        from dnd.core.modifiers import DamageType
        goblin = wrapper.entities["goblin"]
        goblin.health.take_damage(15, DamageType.SLASHING, goblin.uuid)

        menu = _npc_menu(session, actor)
        refusals = self._resolve_each(session, resolver, wrapper, actor, menu)
        assert not refusals, (
            f"{actor} was offered actions the resolver refuses: {refusals}")

    @pytest.mark.parametrize("actor", sorted(CAST))
    def test_every_player_menu_entry_resolves(self, table, actor):
        session, resolver, wrapper, manager = table
        from dnd.core.modifiers import DamageType
        goblin = wrapper.entities["goblin"]
        goblin.health.take_damage(15, DamageType.SLASHING, goblin.uuid)

        menu = _player_menu(session, actor)
        refusals = self._resolve_each(session, resolver, wrapper, actor, menu)
        assert not refusals, (
            f"{actor} was offered actions the resolver refuses: {refusals}")

    def test_the_surges_a_goblin_used_to_be_offered_really_do_fail(self, table):
        """
        Proves the filter is removing real breakage, not hypothetical breakage. If
        these ever start succeeding for a goblin, the gates have been lost and this
        whole file is testing the wrong thing.
        """
        session, resolver, wrapper, _ = table
        from dnd.core.modifiers import DamageType
        goblin = wrapper.entities["goblin"]
        goblin.health.take_damage(15, DamageType.SLASHING, goblin.uuid)

        for surge in ALL_SURGES:
            assert is_offerable(surge) is True, (
                f"{surge} is not even offerable; this test is obsolete")
            wrapper.entities["goblin"].action_economy.reset_all_costs()
            result = resolver.resolve_action({"actor": "goblin",
                                              "action_type": surge,
                                              "target": "windrunner"})
            assert result.get("success") is False, (
                f"a goblin with no Order, no Surgebinding level and no Stormlight "
                f"successfully used {surge}")
            # And specifically because a gate cancelled it, not because of a roll.
            event = result.get("event")
            assert event is None or getattr(event, "canceled", False) is True

    def test_a_missed_attack_does_not_count_as_a_refusal(self, table):
        """
        Guards the helper above against becoming vacuous. `attack` reports
        `success=hit`, so if `_resolve_each` keyed off `success` it would flag every
        unlucky roll as a menu bug — and the fix would be to loosen the assertion
        until it caught nothing. A miss must produce a non-cancelled event.
        """
        session, resolver, wrapper, _ = table
        seen_miss = False
        for _ in range(40):
            wrapper.entities["windrunner"].action_economy.reset_all_costs()
            result = resolver.resolve_action({"actor": "windrunner",
                                              "action_type": "attack",
                                              "target": "goblin"})
            if result.get("success") is False:
                seen_miss = True
                assert result.get("refused") is not True
                assert result.get("event") is not None
                assert getattr(result["event"], "canceled", False) is False
                break
        if not seen_miss:
            pytest.skip("40 attacks all hit; nothing to assert about misses")
