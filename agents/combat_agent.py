"""
Combat Agent - Main Combat Orchestration Agent

CRITICAL: This agent runs ENTIRE combat in one call.
Does NOT return to orchestrator between turns.

Process:
1. Initialize combat (NPCs, initiative)
2. Run combat loop (internal turn management)
3. Clean up and return final result
"""

from typing import Dict, Any
from haystack import component

from components.combat.combat_initializer import CombatInitializer
from components.combat.combat_session_manager import CombatSessionManager
from components.combat.combat_action_resolver import CombatActionResolver
from components.combat.combat_narrative_generator import CombatNarrativeGenerator
from agents.npc_combat_ai import NPCCombatAI
from config.logging_config import get_logger

logger = get_logger(__name__)


@component
class CombatAgent:
    """
    Main combat orchestration agent.

    CRITICAL: This agent runs ENTIRE combat in one call.
    Does NOT return to orchestrator between turns.

    Process:
    1. Initialize combat (NPCs, initiative)
    2. Run combat loop (internal turn management)
    3. Clean up and return final result
    """

    def __init__(
        self,
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        combat_initializer: CombatInitializer,
        combat_action_resolver: CombatActionResolver,
        combat_narrative_generator: CombatNarrativeGenerator,
        npc_combat_ai: NPCCombatAI
    ):
        """
        Initialize Combat Agent.

        Args:
            game_engine: GameEngine instance
            character_manager: CharacterManager instance
            dnd_engine_wrapper: DnDEngineWrapper instance
            combat_initializer: CombatInitializer instance
            combat_action_resolver: CombatActionResolver instance
            combat_narrative_generator: CombatNarrativeGenerator instance
            npc_combat_ai: NPCCombatAI instance
        """
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.initializer = combat_initializer
        self.action_resolver = combat_action_resolver
        self.narrative_gen = combat_narrative_generator
        self.npc_ai = npc_combat_ai
        self.logger = get_logger(__name__)

    @component.output_types(response=Dict[str, Any])
    def run(self, dto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute COMPLETE combat session.

        Args:
            dto: RequestDTO with:
                - scenario_context: Scenario with combat trigger
                - player_character_id: PC char_id
                - _game_engine_ref: GameEngine reference

        Returns:
            GameResponseDTO with:
                - response_type: "combat_complete"
                - outcome: "victory"|"defeat"|"fled"
                - rounds: 5
                - combat_log: [...]
                - narrative: Combat end narrative
        """
        self.logger.info("⚔️ CombatAgent.run() - Starting complete combat session")

        scenario = dto.get("scenario_context", {})
        player_char_id = dto.get("player_character_id", "")

        # Get game engine reference if not already set
        if not hasattr(self, 'game_engine') or self.game_engine is None:
            self.game_engine = dto.get("_game_engine_ref")

        # Phase 1: Initialize Combat
        self.logger.info("Phase 1: Combat Initialization")
        combat_state = self.initializer.initialize_combat(
            scenario=scenario,
            player_character_ids=[player_char_id]
        )

        if combat_state is None:
            self.logger.warning("Combat initialization failed or no combat trigger")
            return {
                "response": {
                    "response_type": "error",
                    "message": "No combat to initialize"
                }
            }

        # Phase 2: Run Combat Loop
        self.logger.info("Phase 2: Combat Loop (internal turn management)")

        session_manager = CombatSessionManager(
            combat_state=combat_state,
            game_engine=self.game_engine,
            character_manager=self.character_manager,
            dnd_engine_wrapper=self.dnd_wrapper,
            combat_action_resolver=self.action_resolver,
            combat_narrative_generator=self.narrative_gen,
            npc_ai_agent=self.npc_ai
        )

        combat_result = session_manager.run_combat_loop()

        # Phase 3: Combat End & Cleanup
        self.logger.info("Phase 3: Combat Cleanup")
        self._cleanup_combat(combat_state)

        # Generate end narrative
        end_narrative = self._generate_end_narrative(combat_result)

        # Display to user
        print("\n" + "="*60)
        print(end_narrative)
        print("="*60)

        self.logger.info(f"✅ Combat complete: {combat_result['outcome']} in {combat_result['rounds']} rounds")

        # Update GameEngine
        self._update_game_engine(combat_result)

        return {
            "response": {
                "response_type": "combat_complete",
                "outcome": combat_result["outcome"],
                "rounds": combat_result["rounds"],
                "combat_log": combat_result["combat_log"],
                "narrative": end_narrative
            }
        }

    def _cleanup_combat(self, combat_state: Dict):
        """
        Clean up after combat.

        - Remove TEMPORARY combat NPCs from CharacterManager (enemies spawned during combat)
        - Mark combat as ended in GameEngine
        - Sync final HP to CharacterManager

        IMPORTANT: Only removes hostile combatants marked in combat_state.
        Predefined NPCs loaded at game initialization (e.g., "Kalak", "Nale")
        are PRESERVED unless they were hostile enemies in this specific combat.

        Temporary NPCs have naming pattern like "goblin_001", "orc_002" (generated during combat).
        Persistent NPCs have custom names/IDs and remain in CharacterManager permanently.
        """
        # Get all hostile NPC IDs from this combat encounter
        # (excludes persistent/predefined NPCs unless they were hostile enemies)
        npc_ids = [
            cid for cid, state in combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        # Remove temporary combat NPCs only
        for npc_id in npc_ids:
            self.character_manager.remove_npc(npc_id)

        self.logger.info(f"Removed {len(npc_ids)} NPCs from CharacterManager")

        # Update GameEngine
        if self.game_engine:
            self.game_engine.game_state.combat_state = {
                "in_combat": False,
                "last_combat_outcome": combat_state.get("end_reason", "unknown")
            }

    def _update_game_engine(self, combat_result: Dict):
        """Update GameEngine with combat results"""
        if not self.game_engine:
            return

        # Update narrative context
        if combat_result["outcome"] == "victory":
            self.game_engine.game_state.narrative_context["last_event"] = "Won combat"
        elif combat_result["outcome"] == "defeat":
            self.game_engine.game_state.narrative_context["last_event"] = "Lost combat"

        self.logger.info("Updated GameEngine with combat results")

    def _generate_end_narrative(self, combat_result: Dict) -> str:
        """Generate combat end narrative"""
        outcome = combat_result["outcome"]
        rounds = combat_result["rounds"]

        if outcome == "victory":
            return f"🎉 VICTORY! You defeated your enemies in {rounds} rounds."
        elif outcome == "defeat":
            return f"💀 DEFEAT! You were overwhelmed after {rounds} rounds..."
        elif outcome == "fled":
            return f"🏃 You managed to escape after {rounds} rounds."
        else:
            return f"Combat ended after {rounds} rounds."


# Factory function for easy instantiation
def create_combat_agent(
    game_engine,
    character_manager,
    dnd_engine_wrapper,
    combat_initializer,
    combat_action_resolver,
    combat_narrative_generator,
    npc_combat_ai
):
    """
    Create CombatAgent instance.

    Args:
        game_engine: GameEngine instance
        character_manager: CharacterManager instance
        dnd_engine_wrapper: DnDEngineWrapper instance
        combat_initializer: CombatInitializer instance
        combat_action_resolver: CombatActionResolver instance
        combat_narrative_generator: CombatNarrativeGenerator instance
        npc_combat_ai: NPCCombatAI instance

    Returns:
        CombatAgent instance
    """
    return CombatAgent(
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_engine_wrapper,
        combat_initializer=combat_initializer,
        combat_action_resolver=combat_action_resolver,
        combat_narrative_generator=combat_narrative_generator,
        npc_combat_ai=npc_combat_ai
    )
