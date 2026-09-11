"""
Never offer an action the resolver will refuse.

Five of the nine registered actions needed a parameter that nothing supplied:

    move                 end_position
    lashing              lashing_type, target_direction
    progression_healing  healing_amount
    illumination         illusion_type
    soulcast             target_essence

They were offered anyway — to the player menu AND to the NPC AI. Measured in one
live encounter: **15 of 28 NPC actions were wasted** on `move` and
`progression_healing`. Each was refused for a missing parameter, each cost a real LLM
call, and the actor kept its action economy — so the turn loop spun until the
stall-breaker forced it along ("still has actions after 4 attempts"). The fight
dragged to 11 rounds and the player character died.

Worse on the player side: auto-play picked `progression_healing` at 4/22 HP and lost
the turn entirely. **An offered action that cannot be taken is a trap**, and the
player has no way to know.

UPDATE (2026-09-11) — the four Surges are now OFFERABLE, and that is the point.
Filtering them out was the correct first fix but the wrong end state: it left
`shardblade_attack` as the only usable Surge, so Surgebinding — the setting's central
fantasy — was unreachable in play. Each surge needed exactly one flavour parameter,
and its action class already had a sensible default; the registry simply never passed
one. `param_defaults` now supplies it, so the surges satisfy the filter honestly
rather than by loosening it.

`move` is still correctly excluded: the tactical grid supplies `end_position` through
its own movement path, not the action menu.

The invariant this file protects is unchanged, and is now asserted directly:
**anything offerable must actually resolve.**
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.combat.action_registry import (ACTION_REGISTRY, is_offerable,
                                               offerable_actions,
                                               required_caller_params)


class TestTheRegistryKnowsWhatIsUsable:
    def test_attack_is_offerable(self):
        """The one action that always worked."""
        assert is_offerable("attack") is True

    @pytest.mark.parametrize("action,param", [
        ("move", "end_position"),
    ])
    def test_actions_needing_unsupplied_params_are_not_offerable(self, action, param):
        """
        `move` is the only one left. It genuinely needs `end_position`, and the
        tactical grid supplies that through its own movement path rather than the
        action menu.

        The four Surges used to be here too. They are now offerable because the
        registry carries `param_defaults` for their one flavour parameter each —
        see TestSurgesAreNowOfferable below and
        tests/combat/test_surges_are_playable.py.
        """
        assert is_offerable(action) is False
        assert param in required_caller_params(action)

    @pytest.mark.parametrize("surge,param", [
        ("lashing", "lashing_type"),
        ("progression_healing", "healing_amount"),
        ("illumination", "illusion_type"),
        ("soulcast", "target_essence"),
    ])
    def test_surges_are_now_offerable_via_defaults(self, surge, param):
        """
        THE FIX FLIPPED THESE. Each surge declared a flavour parameter nothing
        supplied, so it was filtered out and a Windrunner never saw "Lash" on their
        turn — only `shardblade_attack` was ever offerable.

        The action classes already had sensible defaults; the registry never passed
        them. Now `param_defaults` does, so the parameter is still DECLARED but no
        longer *required from the caller*.
        """
        from components.combat.action_registry import param_defaults

        assert param in (ACTION_REGISTRY[surge].get("params") or [])
        assert param in param_defaults(surge)
        assert param not in required_caller_params(surge)
        assert is_offerable(surge) is True

    def test_lashing_needs_no_caller_params(self):
        """Was `{lashing_type, target_direction}`; both now default."""
        assert required_caller_params("lashing") == []

    def test_target_and_weapon_slot_do_not_count(self):
        """
        The resolver supplies these itself, so an action needing only them is
        offerable. Counting them would exclude `attack` and leave nothing.
        """
        assert required_caller_params("attack") == []
        assert is_offerable("shardblade_attack") is True

    def test_offerable_is_a_strict_subset(self):
        offerable = offerable_actions()
        assert 0 < len(offerable) < len(ACTION_REGISTRY)
        assert set(offerable) <= set(ACTION_REGISTRY)

    def test_an_unknown_action_is_not_offerable(self):
        assert is_offerable("teleport_to_shadesmar") is False


class TestNeitherConsumerOffersThem:
    """
    Assert the FILTER IS APPLIED, not merely that it exists. A helper nobody calls is
    the failure mode that hid six subsystems in this project.
    """

    def _session(self):
        from components.character_manager import CharacterManager
        from components.combat.combat_action_resolver import CombatActionResolver
        from components.combat.combat_session_manager import CombatSessionManager
        from components.dnd_engine_wrapper import DnDEngineWrapper

        def sheet(char_id, **over):
            base = {
                "character_id": char_id, "name": char_id, "level": 3,
                "ability_scores": {"strength": 14, "dexterity": 12,
                                   "constitution": 12, "intelligence": 10,
                                   "wisdom": 10, "charisma": 10},
                "hit_points": {"current": 20, "maximum": 20, "temporary": 0},
                "armor_class": 13, "character_class": "Radiant",
                "race": "Alethi", "background": "Soldier",
                "equipment": ["Spear"], "proficiency_bonus": 2,
            }
            base.update(over)
            return base

        manager = CharacterManager()
        manager.add_character(sheet("hero"))
        manager.add_character(sheet("foe"))

        class _Engine:
            def __init__(self, character_manager):
                self.character_manager = character_manager
                self.game_state = type("S", (), {"characters": {}})()

            def update_combat_state(self, *a, **k):
                return None

        engine = _Engine(manager)
        wrapper = DnDEngineWrapper(game_engine=engine, character_manager=manager)
        wrapper.set_entity_position("hero", (0, 0))
        wrapper.set_entity_position("foe", (0, 1))

        state = {
            "round_number": 1, "current_turn_index": 0, "combat_log": [],
            "initiative_order": [{"char_id": "hero", "initiative": 20},
                                 {"char_id": "foe", "initiative": 10}],
            "active_combatants": ["hero", "foe"],
            "combatant_states": {
                "hero": {"is_hostile": False, "hp_current": 20, "hp_max": 20,
                         "actions_remaining": 1, "bonus_actions_remaining": 1,
                         "reaction_available": True},
                "foe": {"is_hostile": True, "hp_current": 20, "hp_max": 20,
                        "actions_remaining": 1, "bonus_actions_remaining": 1,
                        "reaction_available": True}},
        }
        resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                        character_manager=manager,
                                        combat_state=state)
        return CombatSessionManager(
            combat_state=state, game_engine=engine, character_manager=manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")

    def test_the_player_menu_excludes_them(self):
        """
        The regression: `progression_healing` was on the menu every round and always
        refused. Auto-play chose it at 4/22 HP and lost the turn.
        """
        session = self._session()
        categories = session._get_available_actions("hero")
        offered = {item.get("action_type")
                   for category in categories.values()
                   for item in (category.get("actions") or [])}
        unusable = {a for a in offered if a and not is_offerable(a)}
        assert not unusable, f"the player menu offers unusable actions: {unusable}"

    def test_the_player_menu_still_offers_something(self):
        """Both directions — filtering must not empty the menu."""
        session = self._session()
        categories = session._get_available_actions("hero")
        offered = [item for category in categories.values()
                   for item in (category.get("actions") or [])]
        assert offered, "the filter removed every action"

    def test_the_npc_ai_context_excludes_them(self):
        session = self._session()
        context = session._build_npc_context("foe")
        unusable = [a for a in context["available_actions"] if not is_offerable(a)]
        assert not unusable, (
            f"the NPC AI is told it can {unusable}, and every such choice is "
            f"refused — 15 of 28 actions were wasted this way in a live fight")

    def test_the_npc_ai_still_has_options(self):
        session = self._session()
        assert session._build_npc_context("foe")["available_actions"], (
            "the NPC has no actions at all, so it can only fall back")

    def test_attack_survives_the_filter_for_both(self):
        """The one action that must never be filtered out."""
        session = self._session()
        assert "attack" in session._build_npc_context("foe")["available_actions"]
