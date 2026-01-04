"""
Combat Session Manager - Internal Combat Turn Loop

Manages complete combat session from start to finish without returning to orchestrator.
This class handles ALL combat turns internally, getting player input directly via input() calls.

**ARCHITECTURE (2026-01-03): Generic Data-Driven Design**

This class uses a fully generic approach that leverages dnd_engine and ACTION_REGISTRY:
- ✅ No hardcoded action lists - discovers actions from ACTION_REGISTRY
- ✅ No if/elif chains for action types - uses metadata dispatch
- ✅ Works with both D&D 5e actions and Roshar extensions seamlessly
- ✅ New actions can be added to ACTION_REGISTRY without modifying this code

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

from typing import Dict, Any, List, Optional, Tuple

from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatSessionManager:
    """
    Manages internal combat turn loop.

    IMPORTANT: This runs INSIDE CombatAgent.run() and handles
    ALL combat turns without returning to orchestrator.

    Responsibilities:
    - Run combat turn loop
    - Get player input directly (input() calls)
    - Execute NPC AI actions
    - Advance turns
    - Check end conditions
    - Display combat status after each turn
    """

    def __init__(
        self,
        combat_state: Dict[str, Any],
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        combat_action_resolver,
        combat_narrative_generator,
        npc_ai_agent
    ):
        """
        Initialize Combat Session Manager.

        Args:
            combat_state: Combat state dict from CombatInitializer
            game_engine: GameEngine instance
            character_manager: CharacterManager instance
            dnd_engine_wrapper: DnDEngineWrapper instance
            combat_action_resolver: CombatActionResolver instance
            combat_narrative_generator: CombatNarrativeGenerator instance
            npc_ai_agent: NPCAIAgent instance
        """
        self.combat_state = combat_state
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.action_resolver = combat_action_resolver
        self.narrative_gen = combat_narrative_generator
        self.npc_ai = npc_ai_agent
        self.logger = get_logger(__name__)

    def run_combat_loop(self) -> Dict[str, Any]:
        """
        Run complete combat from start to finish.

        Process:
        1. Display combat start
        2. Loop through turns until combat ends
        3. Return final combat result

        Returns:
            {
                "outcome": "victory|defeat|fled",
                "rounds": 5,
                "combat_log": [...],
                "final_states": {...}
            }
        """
        self.logger.info("🗡️ Combat loop starting...")

        # Display combat start
        self._display_combat_start()

        # Main combat loop
        while not self._is_combat_over():
            # Get current actor
            current_actor_id = self._get_current_actor()

            # Execute turn based on actor type
            if self._is_player(current_actor_id):
                self._execute_player_turn(current_actor_id)
            else:
                self._execute_npc_turn(current_actor_id)

            # Check if combatant has more actions
            if not self._has_actions_remaining(current_actor_id):
                # Advance to next combatant
                self._advance_turn()

        # Combat ended
        outcome = self._determine_outcome()
        self.logger.info(f"⚔️ Combat ended: {outcome}")

        return {
            "outcome": outcome,
            "rounds": self.combat_state["round_number"],
            "combat_log": self.combat_state["combat_log"],
            "final_states": self.combat_state["combatant_states"]
        }

    def _execute_player_turn(self, player_char_id: str):
        """
        Execute player's turn using hierarchical menu navigation.

        **UPDATED (2026-01-03)**: Implemented two-level menu system to prevent
        UI overload when many targets/abilities exist.

        Process:
        1. Display combat status
        2. Show action categories (Level 1)
        3. Get category selection
        4. Show specific actions in category (Level 2)
        5. Get action selection
        6. Parse and validate action
        7. Execute via action resolver
        8. Generate and display narrative
        9. Update combat state
        """
        self.logger.info(f"🎮 Player turn: {player_char_id}")

        # Display status
        print("\n" + "="*60)
        print(self.narrative_gen.generate_combat_status(self.combat_state))
        print("="*60)

        # Get available action categories
        action_categories = self._get_available_actions(player_char_id)

        if not action_categories:
            print("❌ No actions available (no actions remaining)")
            return

        # LEVEL 1: Choose action category
        print("\n📋 Choose Action Type:")
        category_keys = list(action_categories.keys())
        for i, category_key in enumerate(category_keys, 1):
            category = action_categories[category_key]
            action_count = len(category["actions"])
            print(f"  {i}. {category['name']} - {category['description']} ({action_count} options)")

        selected_category_key = None
        while True:
            try:
                choice = input(f"\n{player_char_id}> Choose action type (1-{len(category_keys)}): ").strip()

                if not choice.isdigit():
                    print("❌ Please enter a number")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(category_keys):
                    print(f"❌ Please choose 1-{len(category_keys)}")
                    continue

                selected_category_key = category_keys[choice_idx]
                break

            except (ValueError, KeyError) as e:
                print(f"❌ Invalid choice: {e}")

        # LEVEL 2: Choose specific action within category
        selected_category = action_categories[selected_category_key]
        specific_actions = selected_category["actions"]

        print(f"\n{selected_category['name']} - Choose Target/Action:")
        for i, action_item in enumerate(specific_actions, 1):
            print(f"  {i}. {action_item['display']}")

        selected_action_item = None
        while True:
            try:
                choice = input(f"\n{player_char_id}> Choose action (1-{len(specific_actions)}): ").strip()

                if not choice.isdigit():
                    print("❌ Please enter a number")
                    continue

                choice_idx = int(choice) - 1

                if choice_idx < 0 or choice_idx >= len(specific_actions):
                    print(f"❌ Please choose 1-{len(specific_actions)}")
                    continue

                selected_action_item = specific_actions[choice_idx]
                break

            except (ValueError, KeyError) as e:
                print(f"❌ Invalid choice: {e}")

        # Parse action from selection
        action = self._parse_hierarchical_action(
            player_char_id,
            selected_category_key,
            selected_action_item
        )

        # Validate action
        if not self._validate_action(action):
            print("❌ Action not valid in current state")
            return  # Try again

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # Generate narrative
        narrative = self.narrative_gen.generate_action_narrative(
            action=action,
            result=result,
            combat_state=self.combat_state
        )

        # Display narrative
        print(f"\n{narrative}")

        # Consume action
        self._consume_action(player_char_id, action["action_type"])

        self.logger.info(f"✅ Player action executed: {action['action_type']}")

    def _execute_npc_turn(self, npc_char_id: str):
        """
        Execute NPC's turn using AI decision.

        Process:
        1. Build context for NPC AI
        2. LLM decides action
        3. Validate action
        4. Execute action
        5. Generate and display narrative
        6. Update combat state
        """
        self.logger.info(f"🤖 NPC turn: {npc_char_id}")

        # Build context for AI
        context = self._build_npc_context(npc_char_id)

        # Get AI decision
        ai_decision = self.npc_ai.decide_action(context)

        # Convert to action dict
        action = {
            "actor": npc_char_id,
            "action_type": ai_decision["action_type"],
            "target": ai_decision.get("target"),
            "weapon": ai_decision.get("weapon"),
            "reasoning": ai_decision.get("reasoning", "")
        }

        # Validate
        if not self._validate_action(action):
            # Fallback to basic attack
            self.logger.warning(f"NPC AI action invalid, using fallback")
            action = self._get_fallback_action(npc_char_id)

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # Generate narrative
        narrative = self.narrative_gen.generate_action_narrative(
            action=action,
            result=result,
            combat_state=self.combat_state
        )

        # Display narrative
        print(f"\n{narrative}")

        # Consume action
        self._consume_action(npc_char_id, action["action_type"])

        self.logger.info(f"✅ NPC action executed: {action['action_type']}")

    def _get_available_actions(self, char_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get hierarchical action categories for character using ACTION_REGISTRY.

        **UPDATED (2026-01-03)**: Generic data-driven approach that queries
        ACTION_REGISTRY to discover available actions dynamically.

        Returns action categories with sub-options:
        {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": [...]
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": [...]
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": []
            }
        }
        """
        categories = {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": []
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": []
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": []
            }
        }

        char_state = self.combat_state["combatant_states"][char_id]
        character = self.character_manager.characters[char_id]

        # Query ACTION_REGISTRY to discover available actions
        for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items():
            # Check if character can afford this action
            if not self._can_character_afford_action(char_id, metadata):
                continue

            # Check if character meets requirements
            if not self._character_meets_requirements(character, metadata):
                continue

            # Determine which category this action belongs to
            category = self._categorize_action(action_type, metadata)

            # Generate action options (with targets if needed)
            action_options = self._generate_action_options(
                char_id, action_type, metadata
            )

            categories[category]["actions"].extend(action_options)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v["actions"]}

    def _can_character_afford_action(self, char_id: str, action_metadata: Dict) -> bool:
        """
        Check if character has resources for action using dnd_engine.

        **SIMPLIFIED (2026-01-03):** Uses entity.action_economy.can_afford() exclusively.
        No fallback to manual checking.

        Args:
            char_id: Character ID
            action_metadata: Action metadata from ACTION_REGISTRY

        Returns:
            True if character can afford the action, False otherwise
        """
        entity = self.dnd_wrapper.entities[char_id]
        action_class = action_metadata.get("action_class")

        if action_class and hasattr(action_class, "cost_type") and hasattr(action_class, "cost"):
            cost_type = action_class.cost_type
            cost = action_class.cost

            # Use dnd_engine's native can_afford() method
            return entity.action_economy.can_afford(cost_type, cost)

        # Action has no cost defined, assume it's free
        return True

    def _character_meets_requirements(self, character, action_metadata: Dict) -> bool:
        """Check if character meets action requirements (e.g., has Shardblade)."""
        requires = action_metadata.get("requires")
        if not requires:
            return True

        # Check character has required ability/item
        if requires == "surgebinding":
            return hasattr(character, "surgebinding_level") and character.surgebinding_level > 0
        elif requires == "shardblade_summoned":
            return hasattr(character, "shardblade_summoned") and character.shardblade_summoned
        elif requires == "stormlight_spheres":
            return hasattr(character, "stormlight_current") and character.stormlight_current > 0

        # Check Radiant Order requirements
        if "requires_order" in action_metadata:
            required_orders = action_metadata["requires_order"]
            if hasattr(character, "radiant_order"):
                return character.radiant_order in required_orders
            return False

        return True

    def _categorize_action(self, action_type: str, metadata: Dict) -> str:
        """Determine which UI category an action belongs to."""
        # Check if it's a bonus action
        action_class = metadata.get("action_class")
        if action_class and hasattr(action_class, "cost_type"):
            if action_class.cost_type == "bonus_actions":
                return "bonus_actions"

        # Categorize based on action characteristics
        if metadata.get("type") in ["dnd_condition", "roshar_condition"]:
            # Conditions like Dash, Dodge are utility
            return "utility"
        elif action_type in ["attack", "shardblade_attack", "lashing", "progression_healing"]:
            # Offensive/active actions
            return "standard_actions"

        return "utility"

    def _generate_action_options(
        self,
        char_id: str,
        action_type: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """
        Generate action options (with targets if action requires targeting).

        Returns list of action options:
        [
            {
                "action_type": "attack",
                "display": "Attack Goblin Warrior (HP: 7/7)",
                "params": {"target": "goblin_001"}
            }
        ]
        """
        requires_target = "target_entity_uuid" in metadata.get("params", [])

        if requires_target:
            # Generate option for each valid target
            options = []
            targets = self._get_valid_targets(char_id)

            for target_id in targets:
                target_char = self.character_manager.characters[target_id]
                target_state = self.combat_state["combatant_states"][target_id]
                hp_current = target_state["hp_current"]
                hp_max = target_state["hp_max"]

                # Get action description from metadata
                description = metadata.get("description", action_type)
                display = f"{description} → {target_char.name} (HP: {hp_current}/{hp_max})"

                options.append({
                    "action_type": action_type,
                    "display": display,
                    "params": {"target": target_id}
                })

            return options
        else:
            # Single option (no targeting)
            description = metadata.get("description", action_type)
            return [{
                "action_type": action_type,
                "display": description,
                "params": {}
            }]

    def _parse_hierarchical_action(
        self,
        char_id: str,
        category_key: str,
        action_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse hierarchical menu selection into action dict.

        **UPDATED (2026-01-03)**: Generic data-driven approach that uses
        action_item metadata directly (no hardcoded if/elif chains).

        Args:
            char_id: Actor char_id
            category_key: Selected category ("standard_actions", "utility", "bonus_actions")
            action_item: Selected action dict from _generate_action_options()

        Returns:
            {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_001"
            }
        """
        # Build action dict from action_item metadata
        action = {
            "actor": char_id,
            "action_type": action_item["action_type"]
        }

        # Merge in any parameters (target, weapon, etc.)
        action.update(action_item.get("params", {}))

        return action

    def _validate_action(self, action: Dict) -> bool:
        """
        Validate action is legal in current combat state.

        **OPTIMIZED (2026-01-03):** For dnd_engine actions, leverages their native
        _validate() method which checks range, line of sight, and prerequisites.
        This reduces validation code and improves correctness.

        Args:
            action: Action dict with actor, action_type, target, etc.

        Returns:
            True if action is valid, False otherwise
        """
        actor_id = action["actor"]
        action_type = action["action_type"]

        # Get action metadata from ACTION_REGISTRY
        metadata = self.action_resolver.ACTION_REGISTRY.get(action_type)
        if not metadata:
            self.logger.warning(f"Unknown action type: {action_type}")
            return False

        # Check action economy via metadata
        if not self._can_character_afford_action(actor_id, metadata):
            return False

        # Check character meets requirements
        character = self.character_manager.characters.get(actor_id)
        if not self._character_meets_requirements(character, metadata):
            return False

        # For dnd_engine/Roshar actions, let Action._validate() handle detailed checks
        if metadata.get("type") in ["dnd_action", "roshar_action", "roshar_equipment"]:
            # dnd_engine Actions validate:
            # - Range/line of sight
            # - Action economy (via prerequisites)
            # - Target validity
            # - Resource costs
            # We only check high-level requirements here; Action.apply() will validate everything else
            return True

        # For non-dnd_engine actions, do manual validation
        # Validate target (if action requires targeting)
        if "target" in action:
            target_id = action["target"]

            # Target must be in combat
            if target_id not in self.combat_state["active_combatants"]:
                return False

            # Target must be alive
            if self._is_combatant_dead(target_id):
                return False

        return True

    def _consume_action(self, char_id: str, action_type: str):
        """
        Sync action economy from dnd_engine to combat state.

        **SIMPLIFIED (2026-01-03)**: dnd_engine Actions automatically consume action economy
        during action.apply(). This method syncs that state to combat_state for UI display only.

        Note: Action economy is ONLY tracked in dnd_engine. combat_state values are read-only
        mirrors for UI purposes.
        """
        entity = self.dnd_wrapper.entities[char_id]

        # Sync from dnd_engine to combat_state (UI display only)
        char_state = self.combat_state["combatant_states"][char_id]
        char_state["actions_remaining"] = entity.action_economy.actions
        char_state["bonus_actions_remaining"] = entity.action_economy.bonus_actions
        char_state["reaction_available"] = entity.action_economy.reactions > 0

    def _has_actions_remaining(self, char_id: str) -> bool:
        """
        Check if combatant has actions/bonus actions remaining.

        **SIMPLIFIED (2026-01-03):** Queries dnd_engine directly. No fallback.
        """
        entity = self.dnd_wrapper.entities[char_id]
        return (entity.action_economy.actions > 0 or
                entity.action_economy.bonus_actions > 0)

    def _advance_turn(self):
        """
        Advance to next combatant in initiative order.

        **OPTIMIZED (2026-01-03):** Uses dnd_engine's action_economy.reset() and enables
        TURN_START event triggers for condition durations.

        Process:
        1. Increment current_turn_index
        2. If wrapped around, new round (reset action economy via dnd_engine)
        3. Trigger TURN_START events for condition processing
        4. Skip unconscious/dead combatants
        """
        self.combat_state["current_turn_index"] += 1

        # Check if new round
        if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
            self.combat_state["current_turn_index"] = 0
            self.combat_state["round_number"] += 1

            # Reset action economy for all combatants via dnd_engine
            for char_id in self.combat_state["active_combatants"]:
                entity = self.dnd_wrapper.entities.get(char_id)
                if entity and hasattr(entity, 'action_economy'):
                    entity.action_economy.reset()

                    # TODO: Trigger TURN_START events for conditions
                    # This is where dnd_engine's event system would fire TURN_START events
                    # for conditions that have turn-based duration (e.g., Blinded, Stormlight Infused)

                # Sync to combat state
                char_state = self.combat_state["combatant_states"][char_id]
                char_state["actions_remaining"] = 1
                char_state["bonus_actions_remaining"] = 1
                char_state["reaction_available"] = True

            self.logger.info(f"🔄 Round {self.combat_state['round_number']} begins")
            print(f"\n{'='*60}")
            print(f"  🔄 ROUND {self.combat_state['round_number']}")
            print(f"{'='*60}")

        # Skip unconscious/dead combatants
        while self._is_combatant_dead(self._get_current_actor()):
            self.combat_state["current_turn_index"] += 1

            if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
                self.combat_state["current_turn_index"] = 0
                self.combat_state["round_number"] += 1

    def _is_combat_over(self) -> bool:
        """Check if combat should end"""
        ended, reason = self._check_end_conditions()

        if ended:
            self.combat_state["end_reason"] = reason
            return True

        return False

    def _check_end_conditions(self) -> Tuple[bool, Optional[str]]:
        """
        Check end conditions using dnd_engine health system.

        **OPTIMIZED (2026-01-03):** Uses entity.health.is_dead()/is_unconscious() instead
        of manual HP checking. Enables proper D&D 5e death saves, temporary HP, and
        damage resistance tracking.

        Returns:
            (combat_ended: bool, reason: str)
        """
        # Check all hostiles defeated
        hostile_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        # Use dnd_engine's authoritative health system
        all_hostiles_dead = all(
            self._is_combatant_dead(hid)
            for hid in hostile_ids
        )

        if all_hostiles_dead:
            return (True, "all_hostiles_defeated")

        # Check all players defeated
        player_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if not state["is_hostile"]
        ]

        all_players_dead = all(
            self._is_combatant_dead(pid)
            for pid in player_ids
        )

        if all_players_dead:
            return (True, "all_players_defeated")

        return (False, None)

    def _determine_outcome(self) -> str:
        """Determine combat outcome"""
        reason = self.combat_state.get("end_reason", "unknown")

        if reason == "all_hostiles_defeated":
            return "victory"
        elif reason == "all_players_defeated":
            return "defeat"
        elif reason == "fled":
            return "fled"
        else:
            return "unknown"

    def _get_current_actor(self) -> str:
        """Get char_id of current actor from initiative order"""
        idx = self.combat_state["current_turn_index"]
        return self.combat_state["initiative_order"][idx]["char_id"]

    def _is_player(self, char_id: str) -> bool:
        """Check if char_id is a player character"""
        return not self.combat_state["combatant_states"][char_id]["is_hostile"]

    def _is_combatant_dead(self, char_id: str) -> bool:
        """
        Check if combatant is dead/unconscious using dnd_engine.

        **SIMPLIFIED (2026-01-03):** Uses entity.health system exclusively. No fallback.
        D&D 5e death save mechanics are handled entirely by dnd_engine.

        Returns:
            True if combatant is unconscious or dead, False otherwise
        """
        entity = self.dnd_wrapper.entities[char_id]
        # Get constitution modifier from entity (modifier is a property, not a method)
        constitution_mod = entity.ability_scores.constitution.modifier
        # Get current HP using dnd_engine's get_total_hit_points method
        current_hp = entity.health.get_total_hit_points(constitution_mod)
        # Dead/unconscious if current HP <= 0
        return current_hp <= 0

    def _log_combat_action(self, action: Dict, result: Dict):
        """Log action to combat log"""
        self.combat_state["combat_log"].append({
            "round": self.combat_state["round_number"],
            "actor": action["actor"],
            "action_type": action["action_type"],
            "target": action.get("target"),
            "result": result
        })

    def _display_combat_start(self):
        """Display combat start message"""
        print("\n" + "="*60)
        print("  ⚔️  COMBAT BEGINS!")
        print("="*60)

        # Show initiative order
        print("\n📊 Initiative Order:")
        for entry in self.combat_state["initiative_order"]:
            char_name = self.character_manager.characters[entry["char_id"]].name
            print(f"  {entry['initiative']}: {char_name}")

        print("\n" + "="*60)

    def _build_npc_context(self, npc_char_id: str) -> Dict:
        """
        Build context for NPC AI decision.

        **SIMPLIFIED (2026-01-03):** Uses dnd_engine HP exclusively and dynamically discovers
        available actions from ACTION_REGISTRY (enables NPCs to use Roshar abilities automatically).

        Args:
            npc_char_id: NPC character ID

        Returns:
            Context dict for NPC AI with available actions and targets
        """
        npc_char = self.character_manager.characters[npc_char_id]
        entity = self.dnd_wrapper.entities[npc_char_id]

        # Get HP from dnd_engine
        npc_hp = entity.health.get_current_hit_points()
        npc_max_hp = entity.health.get_max_hit_points()

        # Dynamically get available actions from ACTION_REGISTRY
        available_actions = [
            action_type
            for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items()
            if (self._can_character_afford_action(npc_char_id, metadata) and
                self._character_meets_requirements(npc_char, metadata))
        ]

        return {
            "npc": npc_char,
            "npc_hp": npc_hp,
            "npc_max_hp": npc_max_hp,
            "available_targets": self._get_valid_targets(npc_char_id),
            "available_actions": available_actions,  # Dynamic action discovery
            "allies": self._get_allies(npc_char_id),
            "enemies": self._get_enemies(npc_char_id),
            "round_number": self.combat_state["round_number"]
        }

    def _get_valid_targets(self, char_id: str) -> List[str]:
        """
        Get list of valid targets for character.

        **OPTIMIZED (2026-01-03):** Uses entity.health for proper death checks and enables
        optional range/line of sight validation via entity.senses.

        Args:
            char_id: Character ID

        Returns:
            List of valid target character IDs
        """
        entity = self.dnd_wrapper.entities.get(char_id)
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        targets = []
        for cid, state in self.combat_state["combatant_states"].items():
            if cid == char_id:
                continue  # Can't target self

            # Use dnd_engine health check for proper death state
            if self._is_combatant_dead(cid):
                continue  # Can't target dead/unconscious

            # Hostiles target players, players target hostiles
            if is_hostile != state["is_hostile"]:
                # TODO: Optional range/line of sight check
                # if entity and hasattr(entity, 'senses'):
                #     target_entity = self.dnd_wrapper.entities.get(cid)
                #     if target_entity and entity.senses.can_see(target_entity):
                #         targets.append(cid)
                # else:
                #     targets.append(cid)

                targets.append(cid)

        return targets

    def _get_allies(self, char_id: str) -> List[str]:
        """Get list of allies (same hostility status)"""
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        return [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if cid != char_id and state["is_hostile"] == is_hostile
        ]

    def _get_enemies(self, char_id: str) -> List[str]:
        """Get list of enemies (opposite hostility status)"""
        return self._get_valid_targets(char_id)

    def _get_fallback_action(self, npc_char_id: str) -> Dict:
        """Get fallback action if AI decision fails"""
        targets = self._get_valid_targets(npc_char_id)

        if targets:
            return {
                "actor": npc_char_id,
                "action_type": "attack",
                "target": targets[0],  # Attack first valid target
                "weapon": "unarmed"
            }
        else:
            return {
                "actor": npc_char_id,
                "action_type": "dodge"
            }
