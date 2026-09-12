"""
Real-engine combat tests (plan 1.3) — NO MOCKS.

This is the single most important item in Phase 1. The existing suite in
tests/combat/ passes `Mock()` as the dnd_engine wrapper. `Mock` auto-creates
any attribute you touch, so all of these "passed" while being false:

    entity.health.is_dead()          # Health has no is_dead
    action_economy.reset()           # real name is reset_all_costs
    ModifiableValue.value            # real name is normalized_score
    action_class.cost_type           # actions carry a `costs` LIST

That is exactly how five subsystems broke while the plan reported
"121/126 tests passing (96%)". These tests drive the REAL engine, so a
signature drift fails loudly instead of silently passing.

Rule (plan §12): assert on observable end state — HP actually dropped,
the event actually completed — never on "the method was called."
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.character_manager import CharacterManager
from components.dnd_engine_wrapper import DnDEngineWrapper

from dnd.actions import Attack
from dnd.blocks.action_economy import ActionEconomy
from dnd.blocks.equipment import WeaponSlot
from dnd.blocks.health import Health
from dnd.core.values import ModifiableValue


def _character(char_id: str, name: str, **over):
    base = {
        "character_id": char_id,
        "name": name,
        "level": 3,
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 24, "maximum": 24, "temporary": 0},
        "armor_class": 13,
        "character_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
    }
    base.update(over)
    return base


class _StubGameEngine:
    """Minimal stand-in — the wrapper only syncs state back to it."""
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


@pytest.fixture
def wrapper():
    mgr = CharacterManager()
    mgr.add_character(_character("hero", "Hero"))
    mgr.add_character(_character("goblin", "Goblin", armor_class=12))
    return DnDEngineWrapper(game_engine=_StubGameEngine(), character_manager=mgr)


# --------------------------------------------------------------------------
# The engine API the code actually depends on. These would have caught every
# signature bug in finding #6 the day it was introduced.
# --------------------------------------------------------------------------

class TestEngineAPIContract:
    """Pin the real dnd_engine API. Mock() made all of these vacuously true."""

    def test_action_economy_reset_is_reset_all_costs(self):
        assert not hasattr(ActionEconomy, "reset"), \
            "if upstream added reset(), revisit combat_session_manager"
        assert hasattr(ActionEconomy, "reset_all_costs")

    def test_modifiable_value_has_no_dot_value(self):
        assert not hasattr(ModifiableValue, "value"), \
            "code must use .normalized_score, not .value"
        assert hasattr(ModifiableValue, "normalized_score")

    def test_health_has_no_is_dead(self):
        assert not hasattr(Health, "is_dead"), \
            "combat must derive death from get_total_hit_points()"

    def test_take_damage_needs_three_arguments(self):
        import inspect
        params = list(inspect.signature(Health.take_damage).parameters)
        assert params == ["self", "damage", "damage_type", "source_entity_uuid"]

    def test_attack_uses_costs_list_not_cost_type(self):
        assert not hasattr(Attack, "cost_type")
        assert "costs" in Attack.model_fields


# --------------------------------------------------------------------------
# Finding #1: every attack cancelled for want of position/senses.
# --------------------------------------------------------------------------

class TestPositionsAndSenses:
    """1.1 — entities need distinct positions AND populated sense maps."""

    def test_entities_have_distinct_positions(self, wrapper):
        positions = [e.position for e in wrapper.entities.values()]
        assert len(set(positions)) == len(positions), \
            "all entities at the same spot -> line of sight always fails"
        assert (0, 0) not in positions[1:], "second entity still at default origin"

    def test_entities_can_see_each_other(self, wrapper):
        for char_id, entity in wrapper.entities.items():
            assert len(entity.senses.entities) > 0, (
                f"{char_id} has an empty sense map; validate_line_of_sight "
                "will cancel every attack"
            )

    def test_each_entity_senses_the_other(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        assert goblin.uuid in hero.senses.entities
        assert hero.uuid in goblin.senses.entities

    def test_moving_refreshes_senses(self, wrapper):
        assert wrapper.set_entity_position("hero", (5, 5))
        assert wrapper.entities["hero"].position == (5, 5)
        # senses recomputed, not stale
        assert isinstance(wrapper.entities["hero"].senses.entities, dict)

    def test_move_unknown_entity_is_graceful(self, wrapper):
        assert wrapper.set_entity_position("nobody", (1, 1)) is False


# --------------------------------------------------------------------------
# The end-to-end proof: an attack must be able to deal damage.
# --------------------------------------------------------------------------

class TestAttackActuallyLands:
    """
    Plan 1.3's non-negotiable test. Before 1.1 this was impossible:
    every Attack returned EventPhase.CANCEL 'Target entity not in line of sight'.
    """

    def _attack(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        hero.action_economy.reset_all_costs()
        return Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=goblin.uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)

    def test_attack_is_not_cancelled(self, wrapper):
        event = self._attack(wrapper)
        assert event is not None, "attack produced no event"
        assert "CANCEL" not in str(event.phase), (
            f"attack cancelled: {getattr(event, 'status_message', '')}"
        )

    def test_attack_not_blocked_by_line_of_sight(self, wrapper):
        msg = str(getattr(self._attack(wrapper), "status_message", "") or "")
        assert "line of sight" not in msg.lower()

    def test_attack_not_blocked_by_reach(self, wrapper):
        msg = str(getattr(self._attack(wrapper), "status_message", "") or "")
        assert "not in reach" not in msg.lower()

    def test_repeated_attacks_eventually_deal_damage(self, wrapper):
        """
        Statistical, not per-roll: +3 vs AC 12 hits ~60% of the time, so 25
        swings missing entirely would mean damage is not being applied at all.
        """
        goblin = wrapper.entities["goblin"]
        con = 2
        start = goblin.health.get_total_hit_points(con)

        for _ in range(25):
            self._attack(wrapper)

        end = goblin.health.get_total_hit_points(con)
        assert end < start, (
            f"25 attacks dealt zero damage (HP {start} -> {end}); "
            "damage is not reaching the target"
        )

    def test_damage_is_bounded(self, wrapper):
        """Guard against the old `damage *= 2` style crit bug running away."""
        goblin = wrapper.entities["goblin"]
        con = 2
        start = goblin.health.get_total_hit_points(con)
        for _ in range(10):
            self._attack(wrapper)
        dealt = start - goblin.health.get_total_hit_points(con)
        assert 0 <= dealt <= 10 * 30, f"implausible damage total: {dealt}"


class TestActionEconomyEnforced:
    """
    1.2 — the affordability guard checked a field that does not exist, so
    _can_character_afford_action() always returned True.
    """

    def test_action_is_consumed_by_attacking(self, wrapper):
        hero = wrapper.entities["hero"]
        hero.action_economy.reset_all_costs()
        before = hero.action_economy.actions.normalized_score

        Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=wrapper.entities["goblin"].uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)

        assert hero.action_economy.actions.normalized_score < before, \
            "attacking did not consume an action"

    def test_second_attack_same_turn_is_refused(self, wrapper):
        hero = wrapper.entities["hero"]
        goblin = wrapper.entities["goblin"]
        hero.action_economy.reset_all_costs()

        def swing():
            return Attack(
                source_entity_uuid=hero.uuid,
                target_entity_uuid=goblin.uuid,
                weapon_slot=WeaponSlot.MAIN_HAND,
            ).apply(parent_event=None)

        assert swing() is not None
        assert swing() is None, "action economy not enforced within a turn"

    def test_reset_restores_the_action(self, wrapper):
        hero = wrapper.entities["hero"]
        hero.action_economy.reset_all_costs()
        full = hero.action_economy.actions.normalized_score
        Attack(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=wrapper.entities["goblin"].uuid,
            weapon_slot=WeaponSlot.MAIN_HAND,
        ).apply(parent_event=None)
        hero.action_economy.reset_all_costs()
        assert hero.action_economy.actions.normalized_score == full


# --------------------------------------------------------------------------
# End-to-end: a full encounter must reach a decisive outcome.
# This is the plan's Phase 1 exit criterion.
# --------------------------------------------------------------------------

class TestFullEncounterReachesOutcome:
    """
    Drive CombatSessionManager over a real encounter with real entities and a
    real resolver. No mocks in the combat path.

    Before Phase 1 this was impossible three times over: attacks cancelled for
    want of position/senses (1.1), the turn loop spun forever when an economy
    failed to decrease, and _execute_player_turn blocked on input() (1.8).
    """

    def _build(self, monkeypatch):
        from components.character_manager import CharacterManager
        from components.dnd_engine_wrapper import DnDEngineWrapper
        from components.combat.combat_action_resolver import CombatActionResolver
        from components.combat.combat_session_manager import CombatSessionManager

        mgr = CharacterManager()
        mgr.add_character({
            "character_id": "hero", "name": "Hero", "level": 5,
            "ability_scores": {"strength": 18, "dexterity": 14, "constitution": 14,
                               "intelligence": 10, "wisdom": 10, "charisma": 10},
            "hit_points": {"current": 40, "maximum": 40, "temporary": 0},
            "armor_class": 16, "character_class": "Fighter",
            "race": "Human", "background": "Soldier",
            # A real weapon and proficiency: without these the hero fights
            # unarmed at ability modifier alone (~30% vs AC 14), which turns a
            # decisive encounter into a grind and makes timing assertions flaky.
            "equipment": ["Longsword"], "proficiency_bonus": 3,
        })
        # 22 HP / AC 14, matching the Voidbringer Scouts of a live encounter.
        # This was 4 HP / AC 10, which DIED TO ONE HIT — so an encounter ended in
        # ~2 rounds and the turn-loop stall never had time to show. The live
        # combat with these numbers ran 355 iterations across 30 rounds while
        # three tests here reported success.
        mgr.add_character({
            "character_id": "goblin", "name": "Goblin", "level": 2,
            "ability_scores": {"strength": 10, "dexterity": 14, "constitution": 12,
                               "intelligence": 10, "wisdom": 10, "charisma": 8},
            "hit_points": {"current": 22, "maximum": 22, "temporary": 0},
            "armor_class": 14, "character_class": "Goblin",
            "race": "Goblin", "background": "Raider",
            "equipment": ["Spear"], "proficiency_bonus": 2,
        })

        class _StubEngine:
            def __init__(self):
                self.game_state = type("S", (), {"characters": {}})()

        wrapper = DnDEngineWrapper(game_engine=_StubEngine(), character_manager=mgr)
        wrapper.entities["hero"].position = (0, 0)
        wrapper.entities["goblin"].position = (0, 1)
        wrapper.refresh_senses()

        combat_state = {
            "in_combat": True,
            "active_combatants": ["hero", "goblin"],
            "initiative_order": [{"char_id": "hero", "initiative": 20},
                                 {"char_id": "goblin", "initiative": 10}],
            "current_turn_index": 0,
            "round_number": 1,
            "combat_log": [],
            "combatant_states": {
                "hero": {"hp_current": 40, "hp_max": 40, "is_hostile": False,
                         "actions_remaining": 1, "bonus_actions_remaining": 1,
                         "reaction_available": True},
                "goblin": {"hp_current": 22, "hp_max": 22, "is_hostile": True,
                           "actions_remaining": 1, "bonus_actions_remaining": 1,
                           "reaction_available": True},
            },
            "end_conditions": {"all_hostiles_defeated": False,
                               "all_players_defeated": False},
        }

        resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                        character_manager=mgr,
                                        combat_state=combat_state)

        class _Narrative:
            def generate_combat_status(self, state):
                return f"Round {state['round_number']}"
            def generate_action_narrative(self, *a, **k):
                return "..."

        class _NPCAI:
            """Deterministic: always attack the hero."""
            def decide_action(self, context):
                return {"actor": context.get("npc_id", "goblin"),
                        "action_type": "attack", "target": "hero"}
            run = decide_action

        # Silence the menu print()s; choices always pick option 1.
        monkeypatch.setattr("builtins.print", lambda *a, **k: None)

        return CombatSessionManager(
            combat_state=combat_state,
            game_engine=_StubEngine(),
            character_manager=mgr,
            dnd_engine_wrapper=wrapper,
            combat_action_resolver=resolver,
            combat_narrative_generator=_Narrative(),
            npc_ai_agent=_NPCAI(),
            input_provider=lambda prompt: "1",
        ), wrapper

    def test_encounter_terminates(self, monkeypatch):
        """Combat must end on its own, not via the 1000-iteration safety break."""
        manager, _ = self._build(monkeypatch)
        result = manager.run_combat_loop()
        assert result["rounds"] < 100, (
            f"combat ran {result['rounds']} rounds — it is not terminating"
        )

    def test_encounter_reaches_decisive_outcome(self, monkeypatch):
        """
        A 40 HP / AC 16 fighter vs a 4 HP / AC 10 goblin must resolve to
        victory or defeat -- never 'unknown', which is what a stalled loop
        reports.
        """
        manager, _ = self._build(monkeypatch)
        result = manager.run_combat_loop()
        assert result["outcome"] in ("victory", "defeat"), (
            f"expected a decisive outcome, got {result['outcome']!r}"
        )

    def test_damage_was_actually_dealt(self, monkeypatch):
        """Somebody's HP must have changed — otherwise nothing happened."""
        manager, wrapper = self._build(monkeypatch)
        before = {cid: wrapper.get_entity_current_hp(e)
                  for cid, e in wrapper.entities.items()}
        manager.run_combat_loop()
        after = {cid: wrapper.get_entity_current_hp(e)
                 for cid, e in wrapper.entities.items()}
        assert any(after[c] < before[c] for c in before), (
            f"no HP changed during the encounter: {before} -> {after}"
        )

    def test_player_turn_does_not_block_on_stdin(self, monkeypatch):
        """1.8: with a provider injected, nothing reads stdin."""
        manager, _ = self._build(monkeypatch)

        def _explode(*a, **k):
            raise AssertionError("combat read stdin directly")

        monkeypatch.setattr("builtins.input", _explode)
        manager.run_combat_loop()  # must not raise


# --------------------------------------------------------------------------
# Plan 1.5 — conditions. apply_condition() used to be a pure stub that logged
# "(not yet implemented)" and returned None, so 13 of the engine's 15
# conditions were unreachable and no condition ever affected play.
# --------------------------------------------------------------------------

class TestConditions:
    """All 15 engine conditions must actually apply, persist, and remove."""

    ENGINE_CONDITIONS = [
        "blinded", "charmed", "deafened", "frightened", "grappled",
        "incapacitated", "invisible", "paralyzed", "poisoned", "prone",
        "restrained", "stunned", "unconscious", "dodging", "dashing",
    ]

    @pytest.mark.parametrize("condition", ENGINE_CONDITIONS)
    def test_every_engine_condition_applies(self, wrapper, condition):
        assert wrapper.apply_condition("hero", condition) is True, (
            f"{condition!r} failed to apply"
        )

    def test_applied_condition_is_visible(self, wrapper):
        wrapper.apply_condition("hero", "prone")
        assert "Prone" in wrapper.get_conditions("hero")

    def test_condition_names_are_case_insensitive(self, wrapper):
        assert wrapper.apply_condition("hero", "PRONE") is True
        assert "Prone" in wrapper.get_conditions("hero")

    def test_duration_is_recorded(self, wrapper):
        wrapper.apply_condition("hero", "stunned", duration=3)
        stunned = wrapper.entities["hero"].active_conditions["Stunned"]
        assert stunned.duration.duration == 3

    def test_sub_conditions_cascade(self, wrapper):
        """Real 5e: Stunned implies Incapacitated."""
        wrapper.apply_condition("hero", "stunned")
        active = wrapper.get_conditions("hero")
        assert "Stunned" in active
        assert "Incapacitated" in active, "Stunned must cascade to Incapacitated"

    def test_condition_can_be_removed(self, wrapper):
        wrapper.apply_condition("hero", "prone")
        assert wrapper.remove_condition("hero", "prone") is True
        assert "Prone" not in wrapper.get_conditions("hero")

    def test_removing_absent_condition_reports_false(self, wrapper):
        assert wrapper.remove_condition("hero", "stunned") is False

    def test_multiple_conditions_coexist(self, wrapper):
        for c in ("prone", "poisoned", "blinded"):
            wrapper.apply_condition("hero", c)
        active = wrapper.get_conditions("hero")
        assert {"Prone", "Poisoned", "Blinded"} <= set(active)

    def test_roshar_conditions_report_unsupported(self, wrapper):
        """
        Stormlight-infused / spren-bonded are NOT in dnd_engine. Report False
        rather than pretending — callers must be able to tell the difference.
        """
        assert wrapper.apply_condition("hero", "stormlight_infused") is False
        assert wrapper.apply_condition("hero", "spren_bonded") is False

    def test_unknown_character_is_graceful(self, wrapper):
        assert wrapper.apply_condition("nobody", "prone") is False

    def test_conditions_are_per_entity(self, wrapper):
        wrapper.apply_condition("hero", "prone")
        assert "Prone" not in wrapper.get_conditions("goblin")


# --------------------------------------------------------------------------
# Plan 1.4 — real weapons. EquipmentConfig only ever set unarmored_ac and no
# weapon was equipped, so every attack resolved unarmed (1d6 bludgeoning):
# a Shardbearer and a peasant hit equally hard.
# --------------------------------------------------------------------------

class TestWeaponEquipping:
    """Weapon choice must have a mechanical effect."""

    @pytest.fixture
    def armed(self):
        mgr = CharacterManager()
        mgr.add_character(_character(
            "hero", "Hero", level=5,
            ability_scores={"strength": 18, "dexterity": 14, "constitution": 14,
                            "intelligence": 10, "wisdom": 10, "charisma": 10},
            hit_points={"current": 40, "maximum": 40, "temporary": 0},
            equipment=["Greatsword", "rope"],
        ))
        # A high-HP, low-AC dummy so damage totals are measurable
        mgr.add_character(_character(
            "dummy", "Dummy", armor_class=5,
            hit_points={"current": 400, "maximum": 400, "temporary": 0},
        ))
        return DnDEngineWrapper(game_engine=_StubGameEngine(), character_manager=mgr)

    def _swing(self, w, n=20):
        hero, dummy = w.entities["hero"], w.entities["dummy"]
        before = w.get_entity_current_hp(dummy)
        for _ in range(n):
            hero.action_economy.reset_all_costs()
            Attack(source_entity_uuid=hero.uuid, target_entity_uuid=dummy.uuid,
                   weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
        return before - w.get_entity_current_hp(dummy)

    def test_weapon_from_equipment_list_is_equipped(self, armed):
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert main is not None, "no weapon equipped — attacks will resolve unarmed"
        assert main.name == "Greatsword"

    def test_weapon_dice_match_the_weapon(self, armed):
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert (main.dice_numbers, main.damage_dice) == (2, 6), "greatsword is 2d6"

    def test_equipping_a_named_weapon_works(self, armed):
        assert armed.equip_weapon("hero", "Longsword") is True
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert (main.dice_numbers, main.damage_dice) == (1, 8)

    def test_unknown_weapon_is_declined_not_faked(self, armed):
        assert armed.equip_weapon("hero", "Frying Pan of Doom") is False

    def test_substring_match_handles_flavoured_names(self, armed):
        assert armed.equip_weapon("hero", "Kaladin's trusty spear") is True
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert (main.dice_numbers, main.damage_dice) == (1, 6), "spear is 1d6"

    def test_longest_match_wins(self, armed):
        """'greatsword' must not be matched as 'sword'."""
        assert armed.equip_weapon("hero", "greatsword") is True
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert (main.dice_numbers, main.damage_dice) == (2, 6)

    def test_shardblade_is_a_real_weapon(self, armed):
        assert armed.equip_weapon("hero", "Shardblade") is True
        main = armed.entities["hero"].equipment.weapon_main_hand
        assert main.dice_numbers == 4, "a Shardblade should hit far harder than a sword"

    def test_equip_unknown_character_is_graceful(self, armed):
        assert armed.equip_weapon("nobody", "Longsword") is False

    def test_greatsword_outdamages_a_dagger(self, armed):
        """The point of 1.4: weapon choice changes the numbers."""
        armed.equip_weapon("hero", "Greatsword")
        big = self._swing(armed, 40)
        armed.equip_weapon("hero", "Dagger")
        small = self._swing(armed, 40)
        assert big > small, (
            f"greatsword ({big}) should outdamage a dagger ({small}) over 40 swings"
        )

    def test_npc_statblock_attacks_are_equipped(self):
        """npc_stat_generator emits attacks[]; those must reach the engine."""
        mgr = CharacterManager()
        cid = mgr.add_npc({
            "name": "Goblin Warrior", "level": 1,
            "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 10,
                               "intelligence": 10, "wisdom": 8, "charisma": 8},
            "hit_points": {"current": 7, "maximum": 7, "temporary": 0},
            "armor_class": 15, "character_class": "Goblin",
            "race": "Goblin", "background": "Raider",
            "attacks": [{"name": "Scimitar", "attack_bonus": 4,
                         "damage_dice": "1d6", "damage_bonus": 2,
                         "damage_type": "slashing"}],
        })
        w = DnDEngineWrapper(game_engine=_StubGameEngine(), character_manager=mgr)
        main = w.entities[cid].equipment.weapon_main_hand
        assert main is not None and main.name == "Scimitar"
        assert (main.dice_numbers, main.damage_dice) == (1, 6)


# --------------------------------------------------------------------------
# Plan 1.6 — Roshar state on the engine entity.
#
# roshar_actions.py gates every surge on hasattr(entity, 'stormlight_current')
# etc., but those live on CharacterData, never on the dnd_engine Entity. Every
# guard was False: costs unchecked, Stormlight never deducted (free and
# untracked), ShardbladeAttack always "No Shardblade bonded".
#
# Also found here: all three surge classes hand-wrote __init__ without calling
# super().__init__(), so pydantic never initialised the model and constructing
# ANY surge raised AttributeError. No Roshar surge was ever usable.
# --------------------------------------------------------------------------

class TestRosharState:

    @pytest.fixture
    def radiant(self):
        mgr = CharacterManager()
        mgr.add_character(_character(
            "kal", "Kaladin", level=5, character_class="Windrunner",
            hit_points={"current": 40, "maximum": 40, "temporary": 0},
            armor_class=16, radiant_order="Windrunner",
            stormlight_current=8, stormlight_capacity=10, ideal_level=3,
            has_shardblade=True, shardblade_summoned=True, shardblade_name="Syl",
        ))
        mgr.add_character(_character(
            "shal", "Shallan", level=5, character_class="Lightweaver",
            radiant_order="Lightweaver",
            stormlight_current=8, stormlight_capacity=10, ideal_level=3,
        ))
        # An Edgedancer funds the COSTED Regrowth art (2 Investiture Points); the
        # IP pool is the resource the new economy spends (not Stormlight spheres).
        mgr.add_character(_character(
            "lift", "Lift", level=5, character_class="Edgedancer",
            radiant_order="Edgedancer",
            stormlight_current=8, stormlight_capacity=10, ideal_level=3,
            investiture_points={"current": 6, "maximum": 6},
        ))
        mgr.add_character(_character("fused", "Fused", armor_class=13))
        return DnDEngineWrapper(game_engine=_StubGameEngine(), character_manager=mgr)

    @staticmethod
    def _resolver(radiant):
        """A CombatActionResolver over the fixture wrapper (for the IP economy)."""
        from components.combat.combat_action_resolver import CombatActionResolver
        state = {"combatant_states": {cid: {} for cid in radiant.entities}}
        return CombatActionResolver(
            dnd_engine_wrapper=radiant,
            character_manager=radiant.character_manager,
            combat_state=state)

    def test_surge_classes_can_be_constructed(self):
        """All three raised AttributeError before the __init__ fix."""
        from uuid import uuid4
        from components.combat.roshar_actions import (
            Lashing, ShardbladeAttack, ProgressionHealing,
        )
        for cls in (Lashing, ShardbladeAttack, ProgressionHealing):
            obj = cls(source_entity_uuid=uuid4(), target_entity_uuid=uuid4())
            assert obj.name, f"{cls.__name__} did not construct"

    def test_roshar_attrs_reach_the_entity(self, radiant):
        entity = radiant.entities["kal"]
        assert getattr(entity, "radiant_order", None) == "Windrunner"
        assert getattr(entity, "stormlight_current", None) == 8
        assert getattr(entity, "has_shardblade", None) is True

    def test_surgebinding_level_derives_from_ideal_level(self, radiant):
        assert radiant.character_manager.characters["kal"].surgebinding_level == 3

    def test_surge_applies_for_the_right_order(self, radiant):
        from components.combat.roshar_actions import Lashing
        event = Lashing(
            source_entity_uuid=radiant.entities["kal"].uuid,
            target_entity_uuid=radiant.entities["fused"].uuid,
        ).apply()
        assert event is not None and not getattr(event, "canceled", True), (
            f"Windrunner Lashing was rejected: {getattr(event, 'status_message', '?')}"
        )

    def test_surge_consumes_exactly_its_cost(self, radiant):
        """
        Retargeted to the COSTED art (Regrowth = 2 Investiture Points). A free
        cantrip like Lashing now deducts nothing; the resource that IS spent is
        Investiture, through the ledger in CombatActionResolver.
        """
        resolver = self._resolver(radiant)
        pool = radiant.character_manager.characters["lift"].investiture_points
        before = pool["current"]
        result = resolver.resolve_action({
            "actor": "lift", "action_type": "progression_healing",
            "target": "fused"})
        assert result["success"] is True, result
        assert pool["current"] == before - 2, (
            "Regrowth must spend exactly its 2 Investiture Points")
        assert result.get("ip_spent") == 2

    def test_consumption_persists_to_character_data(self, radiant):
        """Investiture lives on CharacterData, so consumption persists with no resync."""
        resolver = self._resolver(radiant)
        resolver.resolve_action({
            "actor": "lift", "action_type": "progression_healing",
            "target": "fused"})
        assert radiant.character_manager.characters["lift"].investiture_points["current"] == 4, (
            "consumption lost — Investiture would be effectively infinite")

    def test_free_cantrip_deducts_no_stormlight(self, radiant):
        """A cantrip is free: Lashing must not deduct Stormlight (was an invented cost)."""
        from components.combat.roshar_actions import Lashing
        entity = radiant.entities["kal"]
        before = entity.stormlight_current
        Lashing(source_entity_uuid=entity.uuid,
                target_entity_uuid=radiant.entities["fused"].uuid).apply()
        assert entity.stormlight_current == before, (
            "a free cantrip must not consume Stormlight")

    def test_wrong_order_is_refused(self, radiant):
        """A Lightweaver cannot Lash."""
        from components.combat.roshar_actions import Lashing
        event = Lashing(
            source_entity_uuid=radiant.entities["shal"].uuid,
            target_entity_uuid=radiant.entities["fused"].uuid,
        ).apply()
        assert event is None or getattr(event, "canceled", False)

    def test_empty_investiture_is_refused(self, radiant):
        """
        Retargeted: an empty Investiture pool refuses the COSTED art (Regrowth),
        while the FREE Lashing cantrip still succeeds with zero Stormlight.
        """
        resolver = self._resolver(radiant)
        radiant.character_manager.characters["lift"].investiture_points["current"] = 0
        result = resolver.resolve_action({
            "actor": "lift", "action_type": "progression_healing",
            "target": "fused"})
        assert result["success"] is False, "Regrowth cast with zero Investiture"
        assert result.get("refused") is True

        # A free cantrip is unaffected by an empty resource pool.
        from components.combat.roshar_actions import Lashing
        radiant.set_roshar_attr("kal", "stormlight_current", 0)
        event = Lashing(
            source_entity_uuid=radiant.entities["kal"].uuid,
            target_entity_uuid=radiant.entities["fused"].uuid,
        ).apply()
        assert event is not None and not getattr(event, "canceled", False), \
            "a free cantrip must remain usable with zero Stormlight"

    def test_spend_stormlight_helper(self, radiant):
        assert radiant.can_afford_stormlight("kal", 5) is True
        assert radiant.spend_stormlight("kal", 5) is True
        assert radiant.character_manager.characters["kal"].stormlight_current == 3
        assert radiant.can_afford_stormlight("kal", 5) is False
        assert radiant.spend_stormlight("kal", 5) is False, "overspend must be refused"
        assert radiant.character_manager.characters["kal"].stormlight_current == 3

    def test_normal_engine_behaviour_is_unaffected(self, radiant):
        """The Roshar mirror must not break ordinary HP handling."""
        assert radiant.get_entity_current_hp(radiant.entities["kal"]) == 40


class TestEncounterIsEfficientNotJustTerminating:
    """
    The three tests above passed while a live combat ran 355 iterations across
    30 rounds without resolving. Two reasons they could not fail:

      1. The stall-breaker force-advances a stuck turn, so combat ALWAYS
         terminates — just 4x slower. `rounds < 100` cannot tell "working" from
         "limping"; the live stall was 30 rounds, comfortably under 100.
      2. The fixture used a 4 HP / AC 10 goblin that died to one hit, so the
         encounter ended before wasted turns accumulated visibly.

    Verified by reintroducing the `actions OR bonus_actions` bug: all three
    passed. These assert on efficiency instead, so the same bug fails here.
    """

    def test_the_stall_breaker_never_fires(self, monkeypatch):
        """
        It is a PRODUCTION safety net. If it fires in a test, some actor's
        economy is not decreasing and the turn logic is broken.
        """
        manager, _ = TestFullEncounterReachesOutcome()._build(monkeypatch)
        result = manager.run_combat_loop()
        assert result["stall_breaks"] == 0, (
            f"the stall-breaker fired {result['stall_breaks']}x — a turn is not "
            f"ending on its own")

    def test_iterations_match_rounds_times_combatants(self, monkeypatch):
        """
        A healthy encounter runs about one iteration per combatant per round.
        The live stall ran ~4x that. Allow 2x headroom for a final partial round
        and for an actor legitimately acting twice.
        """
        manager, _ = TestFullEncounterReachesOutcome()._build(monkeypatch)
        result = manager.run_combat_loop()
        combatants = len(manager.combat_state["active_combatants"])
        budget = max(4, result["rounds"] * combatants * 2)
        assert result["iterations"] <= budget, (
            f"{result['iterations']} iterations for {result['rounds']} rounds "
            f"and {combatants} combatants — roughly "
            f"{result['iterations'] / max(1, result['rounds'] * combatants):.1f}x "
            f"the expected work")

    def test_a_real_enemy_still_dies(self, monkeypatch):
        """
        The old fixture's 4 HP goblin proved nothing. 22 HP / AC 14 needs several
        connecting hits, so this fails if attacks cannot land — the unarmed and
        missing-proficiency bugs both showed up as an unkillable enemy.
        """
        manager, wrapper = TestFullEncounterReachesOutcome()._build(monkeypatch)
        result = manager.run_combat_loop()
        assert result["outcome"] in ("victory", "defeat")
        goblin = manager.combat_state["combatant_states"]["goblin"]
        hero = manager.combat_state["combatant_states"]["hero"]
        assert goblin["hp_current"] <= 0 or hero["hp_current"] <= 0, (
            f"nobody was defeated: goblin {goblin['hp_current']}, "
            f"hero {hero['hp_current']}")

    def test_rounds_are_plausible_for_the_matchup(self, monkeypatch):
        """
        A +4 attacker against AC 14 hits ~55%, so 22 HP falls in a handful of
        rounds. Ten-plus rounds means attacks are not connecting.
        """
        manager, _ = TestFullEncounterReachesOutcome()._build(monkeypatch)
        result = manager.run_combat_loop()
        assert result["rounds"] <= 12, (
            f"{result['rounds']} rounds to resolve a 22 HP enemy — attacks are "
            f"probably not landing")
