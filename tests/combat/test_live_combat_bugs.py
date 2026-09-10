"""
Four bugs a LIVE combat exposed the first time combat ran from gameplay.

Wiring CombatInitializer to combat_trigger made combat reachable for the first
time. It worked — the DM narrated Voidbringers, the LLM extracted 3 enemies,
generated stats (AC 16, HP 65), rolled initiative and ran rounds — and in doing
so surfaced four defects that no isolated test had reached:

1. CombatSessionManager fell back to real input(), so an unattended run blocked
   forever on "Choose action type (1-2):". Plan 1.8 built the input_provider
   seam; CombatAgent never passed one through.
2. ProgressionHealing._apply() reads self.healing_amount, but the field was
   declared only on ProgressionHealingEvent -> AttributeError on first use.
3. Healing offered only ENEMY targets, so it could never heal the wounded
   player at 13/32 HP.
4. Nothing consumed the action economy, so has_actions stayed True and every
   combatant acted four times per turn until the stall-breaker cut them off.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from components.game_engine import GameEngine
from components.dnd_engine_wrapper import DnDEngineWrapper
from components.combat.combat_action_resolver import CombatActionResolver


pytestmark = [pytest.mark.combat, pytest.mark.integration]


def _character(char_id: str, hp: int = 30) -> dict:
    return {
        "character_id": char_id, "name": char_id, "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 12, "constitution": 12,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": hp, "maximum": hp, "temporary": 0},
        "armor_class": 13, "character_class": "Fighter", "race": "Human",
        "background": "Soldier",
    }


@pytest.fixture
def arena():
    """One player and one hostile, positioned adjacent and able to see."""
    engine = GameEngine()
    engine.add_character(_character("Aggi"))
    engine.add_character(_character("Foe"))
    wrapper = DnDEngineWrapper(game_engine=engine,
                               character_manager=engine.character_manager)
    wrapper.set_entity_position("Aggi", (0, 0))
    wrapper.set_entity_position("Foe", (0, 1))
    wrapper.refresh_senses()

    state = {"combatant_states": {
        "Aggi": {"is_hostile": False, "hp_current": 30, "hp_max": 30},
        "Foe": {"is_hostile": True, "hp_current": 30, "hp_max": 30},
    }}
    resolver = CombatActionResolver(dnd_engine_wrapper=wrapper,
                                    character_manager=engine.character_manager,
                                    combat_state=state)
    return engine, wrapper, resolver, state


class TestActionEconomyIsConsumed:
    """Bug 4: has_actions stayed True forever."""

    def test_attacking_spends_the_action(self, arena):
        _, wrapper, resolver, _ = arena
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()

        before = economy.actions.normalized_score
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        after = economy.actions.normalized_score

        assert after < before, (
            "the actor could act again immediately; a live combat gave every "
            "enemy four attacks per round")

    def test_actor_is_out_of_actions_after_acting(self, arena):
        _, wrapper, resolver, _ = arena
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert economy.actions.normalized_score == 0

    def test_reset_restores_the_action(self, arena):
        """A new round must give the action back."""
        _, wrapper, resolver, _ = arena
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        economy.reset_all_costs()
        assert economy.actions.normalized_score >= 1

    def test_no_double_consume_warning(self, arena, caplog):
        """
        dnd_engine's Attack debits the economy itself. Consuming again raised
        "Not enough actions to consume", so the second charge is now guarded.
        """
        import logging

        _, wrapper, resolver, _ = arena
        wrapper.entities["Aggi"].action_economy.reset_all_costs()
        with caplog.at_level(logging.WARNING):
            resolver.resolve_action(
                {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert "Not enough actions" not in caplog.text


class TestProgressionHealingField:
    """Bug 2: AttributeError on first use."""

    def test_healing_amount_is_a_field_on_the_action(self):
        from components.combat.roshar_actions import ProgressionHealing

        assert "healing_amount" in ProgressionHealing.model_fields, (
            "_apply() reads self.healing_amount; without the field pydantic "
            "raises AttributeError")

    def test_default_is_none_so_the_roll_path_runs(self):
        from components.combat.roshar_actions import ProgressionHealing

        assert ProgressionHealing.model_fields["healing_amount"].default is None

    def test_reading_the_attribute_does_not_raise(self, arena):
        """The live crash was on attribute ACCESS, so build a real instance."""
        from components.combat.roshar_actions import ProgressionHealing

        _, wrapper, _, _ = arena
        action = ProgressionHealing(
            source_entity_uuid=wrapper.entities["Aggi"].uuid,
            target_entity_uuid=wrapper.entities["Aggi"].uuid,
        )
        assert action.healing_amount is None


class TestBeneficialActionsTargetAllies:
    """Bug 3: healing was only offered against enemies."""

    def test_healing_targets_include_self(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager
        from components.combat.action_registry import ACTION_REGISTRY

        engine, wrapper, resolver, state = arena
        manager = CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")

        options = manager._generate_action_options(
            "Aggi", "progression_healing", ACTION_REGISTRY["progression_healing"])
        targets = {o["params"]["target"] for o in options}
        assert "Aggi" in targets, "the wounded player could not be healed"
        assert "Foe" not in targets, "healing was offered against an enemy"

    def test_attacks_still_target_enemies(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager
        from components.combat.action_registry import ACTION_REGISTRY

        engine, wrapper, resolver, state = arena
        manager = CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")

        options = manager._generate_action_options(
            "Aggi", "attack", ACTION_REGISTRY["attack"])
        targets = {o["params"]["target"] for o in options}
        assert targets == {"Foe"}


class TestCombatNeverBlocksOnStdin:
    """Bug 1: an unattended run hung on "Choose action type (1-2):"."""

    def test_session_manager_uses_the_injected_provider(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager

        engine, wrapper, resolver, state = arena
        asked = []

        def provider(prompt: str = "") -> str:
            asked.append(prompt)
            return "1"

        manager = CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=provider)

        assert manager.input_provider is provider
        assert manager.input_provider("pick: ") == "1"
        assert asked == ["pick: "]

    def test_combat_agent_forwards_a_provider(self):
        """
        The agent is where the seam was broken: it constructed the session
        manager without passing input_provider, so the default real input() won.
        """
        import inspect
        from agents import combat_agent

        source = inspect.getsource(combat_agent.CombatAgent.run)
        assert "input_provider=" in source, \
            "CombatAgent must pass a provider or an unattended run blocks"

    def test_agent_exposes_an_input_provider_attribute(self):
        import inspect
        from agents import combat_agent

        source = inspect.getsource(combat_agent.CombatAgent.__init__)
        assert "self.input_provider" in source


class TestCombatAgentsHaveRealLLMConfigs:
    """
    Bug adjacent to all of the above: every npc_combat_ai call logged
    "Failed to parse JSON from LLM: Expecting value: line 1 column 1 (char 0)".

    The combat agent names were missing from create_generator's config_map, so
    they silently took default_fallback — which leaves thinking ENABLED, and
    reasoning tokens consumed the whole budget leaving no visible JSON. Every
    NPC therefore fell back to "attack the nearest player" and the tactical AI
    never actually ran.
    """

    def test_npc_combat_ai_disables_thinking(self):
        import config.llm_config as llm_config

        llm_config._global_config_manager = None
        generator = llm_config.get_global_config_manager().create_generator(
            "npc_combat_ai")
        assert generator.generation_config.get("thinking_config") == {
            "thinking_budget": 0}

    def test_combat_init_disables_thinking(self):
        import config.llm_config as llm_config

        llm_config._global_config_manager = None
        generator = llm_config.get_global_config_manager().create_generator(
            "combat_init")
        assert generator.generation_config.get("thinking_config") == {
            "thinking_budget": 0}

    def test_combat_narrative_keeps_thinking(self):
        """Prose benefits from reasoning; only JSON extraction should disable it."""
        import config.llm_config as llm_config

        llm_config._global_config_manager = None
        generator = llm_config.get_global_config_manager().create_generator(
            "combat_narrative")
        assert "thinking_config" not in generator.generation_config

    def test_combat_agents_are_not_silently_defaulted(self):
        import config.llm_config as llm_config

        llm_config._global_config_manager = None
        config = llm_config.get_global_config_manager().config
        for name in ("npc_combat_ai", "combat_init", "combat_narrative"):
            assert getattr(config, name) is not None
            assert getattr(config, name) is not config.default_fallback


class TestLLMSuppliedNumbersAreCoerced:
    """
    A live turn died with "TypeError: 'NoneType' object cannot be interpreted as
    an integer" at `for i in range(count)`.

    The extraction LLM emitted "count": null for "Voidbringer foot soldiers" — an
    unspecified number — and `enemy.get('count', 1)` does NOT protect against a
    present-but-null key, so the default never applied and the whole turn was
    lost before combat began.
    """

    def test_null_count_becomes_one(self):
        from components.combat.combat_initializer import _positive_int
        assert _positive_int(None) == 1

    def test_string_count_is_accepted(self):
        from components.combat.combat_initializer import _positive_int
        assert _positive_int("3") == 3

    def test_nonsense_count_falls_back(self):
        from components.combat.combat_initializer import _positive_int
        assert _positive_int("a horde") == 1
        assert _positive_int(0) == 1
        assert _positive_int(-5) == 1

    def test_absurd_count_is_capped(self):
        """Each enemy costs an LLM call and an entity, so a huge count hangs."""
        from components.combat.combat_initializer import _positive_int
        assert _positive_int(500, maximum=12) == 12

    def test_null_cr_becomes_a_default(self):
        from components.combat.combat_initializer import _positive_float
        assert _positive_float(None) == 0.5
        assert _positive_float("bad") == 0.5
        assert _positive_float(0) == 0.5

    def test_real_cr_survives(self):
        from components.combat.combat_initializer import _positive_float
        assert _positive_float("2.5") == 2.5
        assert _positive_float(3) == 3.0


class TestRefusedActionsDoNotCrash:
    """
    A live combat logged "AttributeError: 'NoneType' object has no attribute
    'canceled'" dozens of times, on every second attack.

    dnd_engine's apply() returns None when it REFUSES an action — usually because
    the actor has no action left. That started happening as soon as the action
    economy was actually being consumed, and `not event.canceled` raised, so the
    resolver reported "Action execution failed" while the narrator still
    described the swing.
    """

    def test_a_refused_action_returns_a_result(self, arena):
        _, wrapper, resolver, _ = arena
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()

        first = resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert first.get("success") in (True, False)

        # Out of actions now: the engine refuses rather than resolving.
        second = resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert isinstance(second, dict)
        assert second["success"] is False

    def test_a_refusal_is_labelled_as_such(self, arena):
        """
        Assert UNCONDITIONALLY. The first version wrapped this in
        `if second.get("refused")`, so when the refusal branch raised NameError
        (action_type was not in scope in _execute_action) the test passed anyway
        and a live combat logged a traceback on every refused action.
        """
        _, wrapper, resolver, _ = arena
        wrapper.entities["Aggi"].action_economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        second = resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})

        assert second["refused"] is True, "the second action should be refused"
        assert "cannot" in second["description"].lower()
        # The names must be resolved, not left as placeholders or missing.
        assert "Aggi" in second["description"]
        assert "attack" in second["description"]

    def test_the_refusal_branch_does_not_raise(self, arena, caplog):
        """The live failure: NameError inside the refusal path itself."""
        import logging

        _, wrapper, resolver, _ = arena
        wrapper.entities["Aggi"].action_economy.reset_all_costs()
        with caplog.at_level(logging.ERROR):
            for _ in range(4):
                resolver.resolve_action(
                    {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert "NameError" not in caplog.text
        assert "not defined" not in caplog.text

    def test_no_attributeerror_is_raised(self, arena):
        """The specific live crash."""
        _, wrapper, resolver, _ = arena
        wrapper.entities["Aggi"].action_economy.reset_all_costs()
        for _ in range(6):
            result = resolver.resolve_action(
                {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
            assert isinstance(result, dict), "resolver raised instead of returning"


class TestCharactersCanActuallyHit:
    """
    A live combat produced TWELVE consecutive misses. Three compounding causes,
    none of them the dice:

      1. Aggi's hardcoded definition had "equipment": [], so
         equip_from_character_data had nothing to equip and every attack
         resolved UNARMED. The narrator, with no real weapon to describe,
         invented a different one each turn — warhammer, spear, greatsword, axe.
      2. STR 8 gave -1 to hit on a melee character.
      3. dnd_engine applies proficiency_bonus to SKILLS ONLY. Grep it: entity.py
         declares the field, skills.py consumes it, actions.py never mentions
         it. So a proficient level 5 character attacked at ability modifier
         alone.

    Together: ~30% against AC 14 where 5e expects ~60%.
    """

    def _armed(self, equipment, strength, proficiency):
        from components.dnd_engine_wrapper import DnDEngineWrapper

        engine = GameEngine()
        engine.add_character({
            "character_id": "Aggi", "name": "Aggi", "level": 5,
            "ability_scores": {"strength": strength, "dexterity": 13,
                               "constitution": 12, "intelligence": 8,
                               "wisdom": 10, "charisma": 13},
            "hit_points": {"current": 32, "maximum": 32, "temporary": 0},
            "armor_class": 14, "character_class": "Radiant", "race": "Alethi",
            "background": "Folk Hero", "equipment": equipment,
            "proficiency_bonus": proficiency,
        })
        engine.add_character(_character("Scout", hp=22))
        wrapper = DnDEngineWrapper(game_engine=engine,
                                   character_manager=engine.character_manager)
        wrapper.set_entity_position("Aggi", (0, 0))
        wrapper.set_entity_position("Scout", (0, 1))
        wrapper.refresh_senses()
        return wrapper

    def _hit_rate(self, wrapper, trials=400):
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        attacker = wrapper.entities["Aggi"]
        target = wrapper.entities["Scout"]
        hits = 0
        for _ in range(trials):
            attacker.action_economy.reset_all_costs()
            event = Attack(source_entity_uuid=attacker.uuid,
                           target_entity_uuid=target.uuid,
                           weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
            if event is not None and "HIT" in str(getattr(event, "attack_outcome", "")):
                hits += 1
        return hits / trials

    def test_a_named_weapon_is_equipped(self):
        wrapper = self._armed(["Spear", "Shield"], 14, 3)
        weapon = wrapper.entities["Aggi"].equipment.weapon_main_hand
        assert weapon is not None, "the character is fighting unarmed"
        assert weapon.name == "Spear"

    def test_non_weapon_equipment_is_skipped(self):
        """Shield and armour must not be equipped as the weapon."""
        wrapper = self._armed(["Leather armor", "Shield", "Spear"], 14, 3)
        assert wrapper.entities["Aggi"].equipment.weapon_main_hand.name == "Spear"

    def test_proficiency_reaches_the_attack_roll(self):
        """The engine never applies it; the wrapper must."""
        weapon = self._armed(["Spear"], 14, 3).entities["Aggi"].equipment.weapon_main_hand
        assert weapon.attack_bonus.score == 3, (
            "proficiency is missing from the attack bonus, so a proficient "
            "character attacks at ability modifier alone")

    def test_hit_rate_is_plausible_for_the_level(self):
        """
        STR 14 (+2) and proficiency (+3) is +5 against AC 14: needs a 9+, so
        about 60%. The floor is deliberately loose to stay robust to dice, but
        tight enough to catch the unarmed/no-proficiency regression at ~30%.
        """
        rate = self._hit_rate(self._armed(["Spear"], 14, 3))
        assert rate > 0.45, f"hit rate {rate:.0%} is too low for +5 vs AC 14"

    def test_the_unarmed_case_is_measurably_worse(self):
        """Confirms the fix is what moved the number, not chance."""
        armed = self._hit_rate(self._armed(["Spear"], 14, 3))
        unarmed = self._hit_rate(self._armed([], 8, 2))
        assert armed > unarmed + 0.10

    def test_the_shipped_characters_carry_weapons(self):
        """
        The real regression: Aggi shipped with "equipment": []. Assert on the
        actual definitions rather than a hand-written copy.
        """
        import inspect

        from core import game_initialization

        source = inspect.getsource(game_initialization)
        assert '"equipment": [],' not in source, (
            "a shipped character has no equipment, so it fights unarmed")


class TestTurnsActuallyEnd:
    """
    A live combat ran 355 iterations across 30 ROUNDS without resolving, the
    stall-breaker firing on every single turn.

    _has_actions_remaining returned `actions > 0 OR bonus_actions > 0`. Every
    action the menu offers costs an ACTION, so spending it left bonus_actions
    untouched at 1 and the check stayed True forever. The turn could never end
    on its own; only the 4-attempt stall-breaker moved play forward, which is why
    each combatant appeared to attack four times per turn.

    This became visible only once the action economy was genuinely being
    consumed — before that, `actions` never decreased either, so the OR was
    hiding behind a second bug.
    """

    def _session(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager

        engine, wrapper, resolver, state = arena
        state.update({
            "active_combatants": ["Aggi", "Foe"],
            "round_number": 1,
            "current_turn_index": 0,
            "initiative_order": [{"char_id": "Aggi", "initiative": 15},
                                 {"char_id": "Foe", "initiative": 10}],
            "combat_log": [],
        })
        return CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")

    def test_the_turn_ends_once_the_action_is_spent(self, arena):
        _, wrapper, resolver, _ = arena
        session = self._session(arena)
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()

        assert session._has_actions_remaining("Aggi") is True
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert session._has_actions_remaining("Aggi") is False, (
            "the turn cannot end; only the stall-breaker would advance play")

    def test_a_leftover_bonus_action_does_not_hold_the_turn_open(self, arena):
        """The exact defect: bonus_actions stays at 1 after an attack."""
        _, wrapper, resolver, _ = arena
        session = self._session(arena)
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})

        assert economy.bonus_actions.normalized_score > 0, (
            "precondition: a bonus action is still available")
        assert session._has_actions_remaining("Aggi") is False, (
            "a leftover bonus action must not keep an exhausted turn alive")

    def test_a_new_round_restores_the_turn(self, arena):
        _, wrapper, resolver, _ = arena
        session = self._session(arena)
        economy = wrapper.entities["Aggi"].action_economy
        economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        economy.reset_all_costs()
        assert session._has_actions_remaining("Aggi") is True


class TestRefusedActionsAreNotNarrated:
    """
    Every refused action still printed a vivid missed sword swing, so the log
    showed a flurry of attacks while mechanically nothing happened — fiction
    contradicting state, which is the drift the DM tools exist to prevent.
    """

    def test_both_turn_paths_check_for_refusal(self):
        import inspect

        from components.combat import combat_session_manager

        source = inspect.getsource(combat_session_manager)
        # One guard in the player path, one in the NPC path.
        assert source.count('result.get("refused")') >= 2, (
            "a refused action would still be narrated as a real attack")

    def test_a_refusal_is_flagged_by_the_resolver(self, arena):
        _, wrapper, resolver, _ = arena
        wrapper.entities["Aggi"].action_economy.reset_all_costs()
        resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        second = resolver.resolve_action(
            {"actor": "Aggi", "action_type": "attack", "target": "Foe"})
        assert second.get("refused") is True


class TestAttackSuccessMeansItHit:
    """
    A live fight ran 5 rounds and ~13 attacks, EVERY ONE narrated "Miss!", with
    nobody losing HP — yet the engine was rolling 65-70% hits and applying damage
    correctly the whole time.

    `success = not event.canceled` means "the event was not cancelled". A miss is
    a perfectly valid, non-cancelled event, so success was True for every attack
    ever resolved. Two consumers read that field:
      - the narrator prints "Hit!"/"Miss!" from it
      - the LLM prompt states "Success: {success}"
    so the model was told every attack succeeded while the printed summary and
    the visible HP disagreed.
    """

    def _resolve(self, arena, trials=40):
        _, wrapper, resolver, _ = arena
        rows = []
        for _ in range(trials):
            wrapper.entities["Aggi"].action_economy.reset_all_costs()
            rows.append(resolver.resolve_action(
                {"actor": "Aggi", "action_type": "attack", "target": "Foe"}))
        return rows

    def test_success_tracks_the_attack_outcome(self, arena):
        from dnd.core.dice import AttackOutcome

        for result in self._resolve(arena):
            outcome = result.get("attack_outcome")
            expected = outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)
            assert result["success"] is expected, (
                f"success={result['success']} but outcome={outcome}")

    def test_misses_are_reported_as_failures(self, arena):
        """The specific defect: a miss reported success=True."""
        from dnd.core.dice import AttackOutcome

        results = self._resolve(arena)
        misses = [r for r in results
                  if r.get("attack_outcome") in (AttackOutcome.MISS,
                                                 AttackOutcome.CRIT_MISS)]
        assert misses, "no misses in 40 attacks — the sample proves nothing"
        assert all(r["success"] is False for r in misses)

    def test_hits_are_reported_as_successes(self, arena):
        from dnd.core.dice import AttackOutcome

        results = self._resolve(arena)
        hits = [r for r in results
                if r.get("attack_outcome") in (AttackOutcome.HIT,
                                               AttackOutcome.CRIT)]
        assert hits, "no hits in 40 attacks — attacks are not landing at all"
        assert all(r["success"] is True for r in hits)

    def test_damage_accompanies_a_hit(self, arena):
        """A reported hit that deals 0 damage would be the same class of lie."""
        results = [r for r in self._resolve(arena) if r["success"]]
        assert results
        assert all(r.get("damage", 0) > 0 for r in results)

    def test_a_miss_deals_no_damage(self, arena):
        results = [r for r in self._resolve(arena) if not r["success"]]
        assert results
        assert all(r.get("damage", 0) == 0 for r in results)


class TestDisplayedHPTracksReality:
    """
    combat_state["hp_current"] was never written back from the engine, so the
    status panel and action menu showed STARTING HP for the whole fight —
    "Voidbringer Scout: 22/22" while it was being wounded. End conditions read
    the engine directly so combat still ended correctly, but the display made a
    working fight look broken and hid the damage that was landing.
    """

    def test_hp_is_mirrored_after_damage(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager

        engine, wrapper, resolver, state = arena
        state.update({"active_combatants": ["Aggi", "Foe"], "round_number": 1,
                      "current_turn_index": 0, "combat_log": [],
                      "initiative_order": [{"char_id": "Aggi", "initiative": 15},
                                           {"char_id": "Foe", "initiative": 10}]})
        session = CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")

        # Land hits until the engine records damage.
        for _ in range(40):
            wrapper.entities["Aggi"].action_economy.reset_all_costs()
            resolver.resolve_action(
                {"actor": "Aggi", "action_type": "attack", "target": "Foe"})

        engine_hp = wrapper.get_entity_current_hp(wrapper.entities["Foe"])
        assert engine_hp < 30, "precondition: the engine recorded damage"

        session._sync_hp_from_engine()
        assert state["combatant_states"]["Foe"]["hp_current"] == engine_hp, (
            "the displayed HP does not match the engine's")

    def test_sync_survives_a_missing_entity(self, arena):
        from components.combat.combat_session_manager import CombatSessionManager

        engine, wrapper, resolver, state = arena
        state.update({"active_combatants": ["Aggi", "Foe"], "round_number": 1,
                      "current_turn_index": 0, "combat_log": [],
                      "initiative_order": []})
        state["combatant_states"]["ghost"] = {"is_hostile": True,
                                             "hp_current": 5, "hp_max": 5}
        session = CombatSessionManager(
            combat_state=state, game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=wrapper, combat_action_resolver=resolver,
            combat_narrative_generator=None, npc_ai_agent=None,
            input_provider=lambda prompt="": "1")
        session._sync_hp_from_engine()  # must not raise
        assert state["combatant_states"]["ghost"]["hp_current"] == 5
