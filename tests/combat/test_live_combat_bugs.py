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
