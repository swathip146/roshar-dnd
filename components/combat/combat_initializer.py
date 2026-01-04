"""
Combat Initializer - Phase 2 of Combat Engine Implementation

Initializes combat state from scenario context, including:
- Enemy parsing from scenario text
- Predefined NPC loading from NPC registry
- NPC stat generation for undefined enemies
- Initiative rolling for all combatants
- Combat state creation

Integrates with:
- NPCStatLoader (for predefined NPCs)
- NPCStatGenerator (for generated NPCs)
- CharacterManager (for NPC storage)
- DnDEngineWrapper (for initiative and combat rules)
- GameEngine (for state management)
"""

import json
import uuid
import random
from typing import Dict, List, Any, Optional
from haystack.dataclasses import ChatMessage

from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatInitializer:
    """
    Initializes combat state from scenario context.

    Process:
    1. Parse scenario for combat trigger and enemy descriptions
    2. Extract enemy info from scene + gm_notes using LLM
    3. Check for predefined NPCs in NPC registry
    4. Generate stats for undefined NPCs via NPCStatGenerator
    5. Add all NPCs to CharacterManager
    6. Sync entities to DnDEngineWrapper
    7. Roll initiative for all combatants
    8. Create combat_state dict
    """

    def __init__(
        self,
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        npc_stat_generator,
        npc_registry,
        llm
    ):
        """
        Initialize CombatInitializer with required components.

        Args:
            game_engine: GameEngine instance (authoritative state)
            character_manager: CharacterManager instance (character data authority)
            dnd_engine_wrapper: DnDEngineWrapper instance (D&D 5e rules)
            npc_stat_generator: NPCStatGenerator instance (generates NPCs)
            npc_registry: NPCStatLoader instance (loads predefined NPCs)
            llm: Haystack LLM generator for scenario parsing
        """
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.npc_generator = npc_stat_generator
        self.npc_registry = npc_registry
        self.llm = llm
        self.logger = get_logger(__name__)

    def initialize_combat(
        self,
        scenario: Dict[str, Any],
        player_character_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize combat from scenario.

        Args:
            scenario: Scenario dict with scene, choices, gm_notes
            player_character_ids: List of PC char_ids participating

        Returns:
            combat_state: Initialized combat state dict, or None if no combat
        """
        self.logger.info("⚔️  Initializing combat...")

        # Step 1: Check if combat should trigger
        if not self._should_trigger_combat(scenario):
            self.logger.warning("   ⚠️  No combat trigger found in scenario")
            return None

        # Step 2: Parse enemies from scenario text
        enemies = self._parse_enemies_from_scenario(scenario)
        self.logger.info(f"   📋 Parsed {len(enemies)} enemy types from scenario")

        if not enemies:
            self.logger.warning("   ⚠️  No enemies extracted from scenario text")
            return None

        # Step 3: Load predefined NPCs from NPC registry
        predefined_npc_ids = self._load_predefined_npcs(enemies)
        self.logger.info(f"   🎭 Loaded {len(predefined_npc_ids)} predefined NPCs")

        # Step 4: Generate undefined NPCs
        generated_npc_ids = self._generate_undefined_npcs(enemies, player_character_ids)
        self.logger.info(f"   🎲 Generated {len(generated_npc_ids)} new NPCs")

        # Step 5: Sync all to DnDEngineWrapper
        if self.dnd_wrapper:
            try:
                self.dnd_wrapper._sync_characters_to_entities()
                self.logger.info("   🔄 Synced all combatants to dnd_engine entities")
            except Exception as e:
                self.logger.warning(f"   ⚠️  Failed to sync to dnd_engine: {e}")

        # Step 6: Roll initiative
        all_combatant_ids = player_character_ids + predefined_npc_ids + generated_npc_ids
        initiative_order = self._roll_initiative(all_combatant_ids)
        init_summary = [f"{entry['char_id']}({entry['initiative']})" for entry in initiative_order[:3]]
        self.logger.info(f"   🎯 Initiative order: {init_summary}...")

        # Step 7: Create combat state
        combat_state = {
            "in_combat": True,
            "combat_id": str(uuid.uuid4()),
            "active_combatants": all_combatant_ids,
            "initiative_order": initiative_order,
            "current_turn_index": 0,
            "round_number": 1,
            "combat_log": [],
            "combatant_states": self._initialize_combatant_states(all_combatant_ids),
            "end_conditions": self._determine_end_conditions(
                player_character_ids,
                predefined_npc_ids + generated_npc_ids
            )
        }

        self.logger.info(f"✅ Combat initialized: {len(all_combatant_ids)} combatants, Round 1")

        return combat_state

    def _should_trigger_combat(self, scenario: Dict[str, Any]) -> bool:
        """
        Check if scenario should trigger combat.

        Checks:
        1. Any choice has combat_trigger=True
        2. Scene text contains combat keywords (fallback)

        Args:
            scenario: Scenario dict

        Returns:
            True if combat should trigger, False otherwise
        """
        # Check choices for combat_trigger flag
        choices = scenario.get('choices', [])
        for choice in choices:
            if choice.get('combat_trigger', False):
                self.logger.debug(f"   ✓ Combat trigger found in choice: {choice.get('title', 'Unknown')}")
                return True

        # Fallback: Check scene text for combat keywords
        scene = scenario.get('scene', '').lower()
        gm_notes = scenario.get('gm_notes', '').lower()
        combined_text = f"{scene} {gm_notes}"

        combat_keywords = [
            'attack', 'combat', 'fight', 'hostile', 'enemy', 'enemies',
            'drawn weapon', 'battle', 'initiative', 'ambush', 'charging'
        ]

        for keyword in combat_keywords:
            if keyword in combined_text:
                self.logger.debug(f"   ✓ Combat keyword found: '{keyword}' (fallback detection)")
                return True

        return False

    def _parse_enemies_from_scenario(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract enemy information from scenario using LLM parsing.

        Scenarios don't have structured enemy data. Instead:
        - scenario['scene']: Narrative text mentioning enemies
        - scenario['gm_notes']: DM notes describing enemies
        - scenario['choices'][*]['combat_trigger']: Boolean flag

        Process:
        1. Combine scene + gm_notes text
        2. Use LLM to extract structured enemy data
        3. Return list of enemy dicts with name, count, CR

        Args:
            scenario: Scenario dict

        Returns:
            List of enemy dicts:
            [
                {
                    "name": "Goblin Warrior",
                    "description": "small goblin with rusty scimitar",
                    "count": 2,
                    "estimated_cr": 0.25,
                    "role": "combatant",
                    "keywords": ["goblin", "warrior", "scimitar"],
                    "is_predefined": False
                }
            ]
        """
        scene_text = scenario.get('scene', '')
        gm_notes = scenario.get('gm_notes', '')
        combined_text = f"Scene: {scene_text}\n\nGM Notes: {gm_notes}"

        # LLM prompt to extract enemy data
        system_prompt = """You are a D&D combat analyzer. Extract enemy/hostile creature information from scenario text.

Output JSON array with enemies:
[
    {
        "name": "Goblin Warrior",
        "description": "small goblin with rusty scimitar",
        "count": 2,
        "estimated_cr": 0.25,
        "role": "combatant",
        "keywords": ["goblin", "warrior", "scimitar"],
        "is_predefined": false
    }
]

Rules:
- Extract enemy type, count, and description
- Estimate CR based on description (goblin=0.25, bandit=0.125, guard=0.125, wolf=0.25, skeleton=0.25, etc.)
- Role: combatant (normal), minion (weak), boss (strong), support (healer/buffer)
- Keywords: words that might match templates or campaign NPCs
- is_predefined: true if named NPC mentioned (e.g., "Kalak", "Nale", "Captain Kholinar"), false otherwise
- If no enemies mentioned, return empty array: []

Output ONLY valid JSON, no markdown formatting."""

        user_prompt = f"""Extract enemy information from this D&D scenario:

{combined_text}

Return JSON array of enemies:"""

        try:
            response = self.llm.run(
                messages=[
                    ChatMessage.from_system(system_prompt),
                    ChatMessage.from_user(user_prompt)
                ]
            )

            # Parse JSON from response
            content = response['replies'][0].content.strip()

            # Handle markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            enemies = json.loads(content)

            if not isinstance(enemies, list):
                self.logger.warning("   ⚠️  LLM returned non-list response, using empty list")
                enemies = []

            self.logger.debug(f"   Extracted {len(enemies)} enemy types: {[e.get('name', 'Unknown') for e in enemies]}")

            return enemies

        except json.JSONDecodeError as e:
            self.logger.error(f"   ❌ Failed to parse enemies from LLM response: {e}")
            self.logger.debug(f"   LLM response: {content[:200] if 'content' in locals() else 'N/A'}")
            return []
        except Exception as e:
            self.logger.error(f"   ❌ Failed to extract enemies from scenario: {e}")
            return []

    def _load_predefined_npcs(self, enemies: List[Dict[str, Any]]) -> List[str]:
        """
        Load NPCs from NPC registry if they match enemy names.

        Checks:
        1. NPCStatLoader (npc_registry) for name matches
        2. If enemy is_predefined=True

        Args:
            enemies: List of enemy dicts from _parse_enemies_from_scenario

        Returns:
            List of char_ids for predefined NPCs added to CharacterManager
        """
        predefined_ids = []

        if not self.npc_registry:
            self.logger.warning("   ⚠️  No NPC registry available, skipping predefined NPC loading")
            return predefined_ids

        for enemy in enemies:
            if not enemy.get('is_predefined', False):
                continue

            enemy_name = enemy.get('name', '')

            # Try to load from NPC registry (uses case-insensitive + partial matching)
            npc_stats = self.npc_registry.get_npc_by_name(enemy_name)

            if npc_stats:
                # Found predefined NPC - add to CharacterManager
                char_id = self.character_manager.add_npc(npc_stats)
                predefined_ids.append(char_id)

                self.logger.info(f"      ✅ Loaded predefined NPC: {npc_stats['name']} ({char_id})")

                # Mark as processed so we don't generate it
                enemy['processed'] = True
            else:
                self.logger.warning(f"      ⚠️  No NPC file found for '{enemy_name}', will generate")
                enemy['is_predefined'] = False  # Fallback to generation

        return predefined_ids

    def _generate_undefined_npcs(
        self,
        enemies: List[Dict[str, Any]],
        player_character_ids: List[str]
    ) -> List[str]:
        """
        Generate NPC stats for undefined enemies.

        For each enemy not processed by _load_predefined_npcs:
        1. Generate stats via NPCStatGenerator
        2. Create multiple instances if count > 1
        3. Add to CharacterManager

        Args:
            enemies: List of enemy dicts
            player_character_ids: List of PC IDs for CR balancing

        Returns:
            List of char_ids for generated NPCs
        """
        generated_ids = []

        # Get party level for CR balancing
        party_level = self._get_party_level(player_character_ids)

        for enemy in enemies:
            if enemy.get('processed', False):
                continue  # Skip predefined NPCs

            count = enemy.get('count', 1)
            enemy_name = enemy.get('name', 'Unknown Creature')

            # Generate stats once (use template if available)
            try:
                npc_stats = self.npc_generator.generate_npc_stats(
                    npc_description=enemy.get('description', enemy_name),
                    challenge_rating=enemy.get('estimated_cr', 0.5),
                    role=enemy.get('role', 'combatant'),
                    context={
                        'party_level': party_level,
                        'enemy_count': count,
                        'keywords': enemy.get('keywords', [])
                    }
                )
            except Exception as e:
                self.logger.error(f"      ❌ Failed to generate NPC '{enemy_name}': {e}")
                continue

            # Create multiple instances if needed
            for i in range(count):
                # Add to CharacterManager (adds unique suffix if count > 1)
                char_id = self.character_manager.add_npc(npc_stats)
                generated_ids.append(char_id)

                self.logger.info(f"      ✅ Generated NPC {i+1}/{count}: {char_id} (CR {enemy.get('estimated_cr', '?')})")

        return generated_ids

    def _roll_initiative(self, combatant_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Roll initiative for all combatants using DnDEngineWrapper.

        Args:
            combatant_ids: List of character IDs

        Returns:
            Sorted list (high to low):
            [
                {"char_id": "aggi", "initiative": 18},
                {"char_id": "goblin_001", "initiative": 15},
                ...
            ]
        """
        initiative_rolls = []

        if not self.dnd_wrapper:
            # Fallback: manual initiative rolls without dnd_engine
            self.logger.warning("   ⚠️  No dnd_engine_wrapper, using fallback initiative")
            return self._roll_initiative_fallback(combatant_ids)

        try:
            from dnd.enums import RollType
        except ImportError:
            self.logger.warning("   ⚠️  dnd.enums not available, using fallback initiative")
            return self._roll_initiative_fallback(combatant_ids)

        for char_id in combatant_ids:
            try:
                entity = self.dnd_wrapper.entities.get(char_id)

                if not entity:
                    self.logger.warning(f"      ⚠️  Entity not found for {char_id}, using fallback")
                    # Fallback: use character data directly
                    char = self.character_manager.characters.get(char_id)
                    if char:
                        dex_mod = (char.ability_scores.get('dexterity', 10) - 10) // 2
                        initiative = self._roll_d20() + dex_mod
                    else:
                        initiative = self._roll_d20()
                else:
                    # Get DEX modifier from entity
                    dex_mod = entity.ability_modifier("dexterity")

                    # Roll d20 + DEX mod
                    roll_result = entity.roll_d20(dex_mod, RollType.CHECK)
                    initiative = roll_result.total

                initiative_rolls.append({
                    "char_id": char_id,
                    "initiative": initiative
                })

                self.logger.debug(f"      {char_id} initiative: {initiative}")

            except Exception as e:
                self.logger.warning(f"      ⚠️  Failed to roll initiative for {char_id}: {e}")
                # Fallback: d20 + 0
                initiative_rolls.append({
                    "char_id": char_id,
                    "initiative": self._roll_d20()
                })

        # Sort by initiative (high to low), then by DEX modifier for ties
        initiative_rolls.sort(key=lambda x: x['initiative'], reverse=True)

        return initiative_rolls

    def _roll_initiative_fallback(self, combatant_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fallback initiative rolling without dnd_engine.

        Uses CharacterManager data to calculate DEX modifiers.

        Args:
            combatant_ids: List of character IDs

        Returns:
            Sorted initiative list
        """
        initiative_rolls = []

        for char_id in combatant_ids:
            char = self.character_manager.characters.get(char_id)

            if char:
                # Calculate DEX modifier
                dex_score = char.ability_scores.get('dexterity', 10)
                dex_mod = (dex_score - 10) // 2

                # Roll d20 + DEX
                d20_roll = random.randint(1, 20)
                initiative = d20_roll + dex_mod
            else:
                # No character data, just roll d20
                initiative = random.randint(1, 20)

            initiative_rolls.append({
                "char_id": char_id,
                "initiative": initiative
            })

            self.logger.debug(f"      {char_id} initiative: {initiative}")

        # Sort by initiative (high to low)
        initiative_rolls.sort(key=lambda x: x['initiative'], reverse=True)

        return initiative_rolls

    def _roll_d20(self) -> int:
        """Roll a d20."""
        return random.randint(1, 20)

    def _initialize_combatant_states(self, combatant_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Create per-combatant state tracking.

        Args:
            combatant_ids: List of character IDs

        Returns:
            Dict mapping char_id to state dict:
            {
                "aggi": {
                    "hp_current": 25,
                    "hp_max": 25,
                    "conditions": [],
                    "actions_remaining": 1,
                    "bonus_actions_remaining": 1,
                    "reaction_available": True,
                    "is_hostile": False
                },
                "goblin_001": {
                    "hp_current": 7,
                    "hp_max": 7,
                    ...
                    "is_hostile": True
                }
            }
        """
        states = {}

        for char_id in combatant_ids:
            char = self.character_manager.characters.get(char_id)

            if not char:
                self.logger.warning(f"   ⚠️  Character {char_id} not found in CharacterManager")
                continue

            # Determine if hostile (NPCs are hostile by default, PCs are not)
            # NPCs have suffixes like "_001", "_002", or start with "npc_"
            is_npc = (
                any(char_id.endswith(f"_{i:03d}") for i in range(1, 100)) or
                char_id.startswith("npc_") or
                char_id in self.character_manager.get_npcs()
            )

            # Get HP from character data
            hp_data = char.hit_points
            if isinstance(hp_data, dict):
                hp_current = hp_data.get('current', hp_data.get('maximum', 1))
                hp_max = hp_data.get('maximum', 1)
            else:
                # Fallback: integer HP
                hp_current = hp_data
                hp_max = hp_data

            states[char_id] = {
                "hp_current": hp_current,
                "hp_max": hp_max,
                "conditions": [],
                "actions_remaining": 1,
                "bonus_actions_remaining": 1,
                "reaction_available": True,
                "is_hostile": is_npc
            }

        return states

    def _determine_end_conditions(
        self,
        player_ids: List[str],
        npc_ids: List[str]
    ) -> Dict[str, bool]:
        """
        Determine combat victory/defeat conditions.

        Default conditions:
        - all_hostiles_defeated: All NPCs at 0 HP
        - all_players_defeated: All PCs at 0 HP

        Args:
            player_ids: List of PC character IDs
            npc_ids: List of NPC character IDs

        Returns:
            Dict of end condition flags
        """
        return {
            "all_hostiles_defeated": False,
            "all_players_defeated": False,
            "objective_achieved": False,
            "fled": False
        }

    def _get_party_level(self, player_character_ids: List[str]) -> int:
        """
        Get average party level for CR balancing.

        Args:
            player_character_ids: List of PC character IDs

        Returns:
            Average party level (integer)
        """
        if not player_character_ids:
            return 1

        levels = []
        for char_id in player_character_ids:
            char = self.character_manager.characters.get(char_id)
            if char:
                levels.append(char.level)

        if not levels:
            return 1

        return sum(levels) // len(levels)


# Convenience function for creating CombatInitializer
def create_combat_initializer(
    game_engine,
    character_manager,
    dnd_engine_wrapper,
    npc_stat_generator,
    npc_registry,
    llm
) -> CombatInitializer:
    """
    Factory function to create CombatInitializer instance.

    Args:
        game_engine: GameEngine instance
        character_manager: CharacterManager instance
        dnd_engine_wrapper: DnDEngineWrapper instance
        npc_stat_generator: NPCStatGenerator instance
        npc_registry: NPCStatLoader instance
        llm: Haystack LLM generator

    Returns:
        CombatInitializer instance
    """
    return CombatInitializer(
        game_engine=game_engine,
        character_manager=character_manager,
        dnd_engine_wrapper=dnd_engine_wrapper,
        npc_stat_generator=npc_stat_generator,
        npc_registry=npc_registry,
        llm=llm
    )
