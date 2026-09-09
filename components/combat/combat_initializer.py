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
        player_character_ids: List[str],
        force_combat: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Initialize combat from scenario.

        Args:
            scenario: Scenario dict with scene, choices, gm_notes
            player_character_ids: List of PC char_ids participating
            force_combat: If True, skip combat trigger check (used when routed via combat_pipeline)

        Returns:
            combat_state: Initialized combat state dict, or None if no combat
        """
        self.logger.info("⚔️  Initializing combat...")

        # Step 1: Check if combat should trigger (skip if force_combat=True)
        if not force_combat and not self._should_trigger_combat(scenario):
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

        # Build list of all combatants BEFORE trying to use it
        all_combatant_ids = player_character_ids + predefined_npc_ids + generated_npc_ids

        # Step 5: Sync all to DnDEngineWrapper
        if self.dnd_wrapper:
            try:
                self.dnd_wrapper._sync_characters_to_entities()
                self.logger.info("   🔄 Synced all combatants to dnd_engine entities")

                # LOG ALL ENTITY STATS AFTER SYNC
                self.logger.info("   📊 ENTITY STATS AFTER SYNC:")
                for char_id in all_combatant_ids:
                    char = self.character_manager.characters.get(char_id)
                    entity = self.dnd_wrapper.entities.get(char_id)

                    if char:
                        self.logger.info(f"      {char_id} (CharacterManager):")
                        self.logger.info(f"         Name: {char.name}")
                        self.logger.info(f"         Level: {char.level}")
                        self.logger.info(f"         HP: {char.hit_points}")
                        self.logger.info(f"         Ability Scores: {char.ability_scores}")

                    if entity:
                        constitution_mod = entity.ability_scores.constitution.modifier
                        # Must include max_hit_points_bonus (plan 1.7)
                        max_hp = self.dnd_wrapper.get_entity_max_hp(entity)
                        total_hp = entity.health.get_total_hit_points(constitution_mod)
                        damage_taken = entity.health.damage_taken

                        self.logger.info(f"      {char_id} (dnd_engine Entity):")
                        self.logger.info(f"         Constitution Mod: {constitution_mod}")
                        self.logger.info(f"         Max HP (from hit dice): {max_hp}")
                        self.logger.info(f"         Damage Taken: {damage_taken}")
                        self.logger.info(f"         Total HP (max - damage): {total_hp}")
                        self.logger.info(f"         Is Dead: {total_hp <= 0}")
                    else:
                        self.logger.warning(f"      ❌ {char_id} has no entity in dnd_wrapper!")

            except Exception as e:
                self.logger.warning(f"   ⚠️  Failed to sync to dnd_engine: {e}")

        # Step 6: Roll initiative (all_combatant_ids already defined above)
        initiative_order = self._roll_initiative(all_combatant_ids)

        # Log full initiative order for debugging
        self.logger.info(f"   🎯 Full initiative order ({len(initiative_order)} combatants):")
        for i, entry in enumerate(initiative_order, 1):
            self.logger.info(f"      {i}. {entry['char_id']} (initiative: {entry['initiative']})")

        # Step 6.5: Place combatants on the grid and refresh senses (plan 1.1).
        # Without this, NPCs generated mid-combat keep the default position and
        # stale sense maps, so validate_line_of_sight/reach rejects their
        # attacks -- observed as goblins that attack every round and ALWAYS miss.
        self._position_combatants(player_character_ids,
                                  predefined_npc_ids + generated_npc_ids)

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

    def _position_combatants(self, player_ids: List[str], hostile_ids: List[str]) -> None:
        """
        Place combatants on the grid and refresh senses (plan 1.1).

        Players form a line at y=0, hostiles face them at y=1 — adjacent, so
        melee reach (5 ft = 1 tile) is satisfied from the first round. Senses
        are recomputed once at the end, because
        Entity.update_all_entities_senses() is global and each entity's sense
        map must include everyone created before AND after it.

        Skipping this left mid-combat NPCs at the default position with empty
        sense maps, so every one of their attacks was rejected for line of
        sight / reach — visible in play as enemies that always miss.
        """
        wrapper = self.dnd_wrapper
        if wrapper is None:
            self.logger.warning("   ⚠️ No dnd_engine wrapper; skipping positioning")
            return

        placed = 0
        for row, group in ((0, player_ids), (1, hostile_ids)):
            for column, char_id in enumerate(group):
                entity = wrapper.entities.get(char_id)
                if entity is None:
                    self.logger.warning(f"   ⚠️ No entity for {char_id}; cannot position")
                    continue
                entity.position = (column, row)
                placed += 1

        # One global refresh AFTER all placements
        if hasattr(wrapper, "refresh_senses"):
            wrapper.refresh_senses()

        self.logger.info(
            f"   📍 Positioned {placed} combatant(s) and refreshed senses "
            f"(players at y=0, hostiles at y=1)"
        )

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

    def _campaign_encounters(self) -> List[Dict[str, Any]]:
        """Authored encounters from the campaign file, loaded once."""
        cached = getattr(self, "_encounters_cache", None)
        if cached is not None:
            return cached

        encounters: List[Dict[str, Any]] = []
        try:
            import json
            from pathlib import Path

            campaign = getattr(self.game_engine, "campaign_config", None)
            source = getattr(campaign, "source_file", None) if campaign else None
            if source:
                path = Path(source)
                if path.exists() and path.suffix == ".json":
                    data = json.loads(path.read_text())
                    # Only STRUCTURED encounters are usable: the older format was
                    # prose only (title/type/description/challenge) with no enemy
                    # roster, so it cannot drive combat.
                    encounters = [e for e in (data.get("encounters") or [])
                                  if isinstance(e, dict) and "enemies" in e]
        except Exception as e:
            self.logger.debug(f"   Could not load campaign encounters: {e}")

        self._encounters_cache = encounters
        if encounters:
            self.logger.info(f"   📜 {len(encounters)} authored encounter(s) available")
        return encounters

    def _match_authored_encounter(self, scenario: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the authored encounter this scene is describing, if any.

        Scored on three signals, strongest first:
          - the current location matches the encounter's location
          - the encounter's quest is still pending
          - trigger keywords appear in the scene / gm_notes / chosen option

        Requires a keyword hit so an encounter cannot fire merely for being in
        the right place; returns None when nothing matches, and combat falls back
        to LLM extraction.
        """
        encounters = self._campaign_encounters()
        if not encounters:
            return None

        haystack = " ".join(str(scenario.get(key, "")) for key in
                            ("scene", "gm_notes", "player_choice")).lower()
        for choice in (scenario.get("choices") or []):
            if isinstance(choice, dict):
                haystack += " " + str(choice.get("title", "")).lower()
                haystack += " " + str(choice.get("description", "")).lower()

        location = ""
        pending: set = set()
        try:
            location = str(self.game_engine.get_location_context().get(
                "current_location", "")).lower()
        except Exception:
            pass
        try:
            progress = self.game_engine.get_quest_progress()
            pending = {str(o).lower() for o in (progress.get("pending") or [])}
        except Exception:
            pass

        best, best_score = None, 0
        for encounter in encounters:
            trigger = encounter.get("trigger") or {}
            keywords = [str(k).lower() for k in (trigger.get("keywords") or [])]
            hits = sum(1 for keyword in keywords if keyword and keyword in haystack)
            if not hits:
                continue  # location alone must never fire an encounter

            score = hits
            wanted_location = str(trigger.get("location", "")).lower()
            if wanted_location and wanted_location == location:
                score += 3
            quest_title = str(encounter.get("victory", {}).get(
                "quest_objective", "")).lower()
            if quest_title and quest_title in pending:
                score += 2

            if score > best_score:
                best, best_score = encounter, score

        if best is not None:
            self.logger.debug(
                f"   📜 matched encounter '{best.get('id')}' (score {best_score})")
        return best

    def _parse_enemies_from_scenario(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract enemy information from scenario using LLM parsing.

        Scenarios don't have structured enemy data. Instead:
        - scenario['scene']: Narrative text mentioning enemies
        - scenario['gm_notes']: DM notes describing enemies
        - scenario['choices'][*]['combat_trigger']: Boolean flag
        - scenario['player_choice']: What player chose that led to combat (NEW)
        - scenario['full_context']: Full previous scenario + player choice (NEW)

        Process:
        1. Combine scene + gm_notes + player_choice + all choice options
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
        # AUTHORED ENCOUNTERS WIN. The campaign may define an encounter with a
        # fixed roster; prefer it over asking the LLM to invent one from prose.
        # Extraction produced CR 3 x3 for a level 1 party in a live run, because
        # it reads "Voidbringers" and guesses. An authored roster cannot drift.
        authored = self._match_authored_encounter(scenario)
        if authored is not None:
            enemies = authored.get("enemies") or []
            self.logger.info(
                f"   📜 Using authored encounter '{authored.get('id')}' "
                f"({len(enemies)} enemy type(s))")
            if not enemies:
                # A deliberately non-combat encounter (a social trial). Returning
                # [] tells initialize_combat there is no fight here, which is the
                # authored intent rather than a parsing failure.
                self.logger.info(
                    f"   📜 '{authored.get('id')}' is authored with NO enemies "
                    f"— this scene is not a fight")
            return [dict(enemy) for enemy in enemies]

        scene_text = scenario.get('scene', '')
        gm_notes = scenario.get('gm_notes', '')
        player_choice = scenario.get('player_choice', '')

        # Get all choice options to provide full context
        choices = scenario.get('choices', [])
        choices_text = ""
        if choices:
            choices_text = "\n\nAvailable choices player saw:\n"
            for i, choice in enumerate(choices, 1):
                title = choice.get('title', f'Option {i}')
                desc = choice.get('description', '')
                choices_text += f"{i}. {title}"
                if desc:
                    choices_text += f" - {desc}"
                choices_text += "\n"

        # Build comprehensive context for LLM
        combined_text = f"""PREVIOUS DM SCENARIO:
{scene_text}

GM NOTES:
{gm_notes}

{choices_text}

PLAYER CHOSE:
{player_choice}
"""

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
- Extract enemy type, count, and description from the DM's scenario narrative
- Estimate CR based on description (goblin=0.25, bandit=0.125, guard=0.125, wolf=0.25, skeleton=0.25, Voidbringer=3-5, etc.)
- Role: combatant (normal), minion (weak), boss (strong), support (healer/buffer)
- Keywords: words that might match templates or campaign NPCs
- is_predefined: true if named NPC mentioned (e.g., "Kalak", "Nale", "Captain Kholinar"), false otherwise
- If no enemies mentioned, return empty array: []
- Look at ALL the text: scene, GM notes, choices, and what player chose

Output ONLY valid JSON, no markdown formatting."""

        user_prompt = f"""Extract enemy information from this D&D scenario:

{combined_text}

Return JSON array of enemies:"""

        # Enhanced logging to debug enemy extraction
        self.logger.info("📋 Calling LLM to extract enemies from scenario...")
        self.logger.info(f"   Scene text length: {len(scene_text)} chars")
        self.logger.info(f"   GM notes length: {len(gm_notes)} chars")
        self.logger.info(f"   Player choice length: {len(player_choice)} chars")
        self.logger.info(f"   Combined text length: {len(combined_text)} chars")
        self.logger.debug(f"   Scene: {scene_text[:200]}")
        self.logger.debug(f"   GM notes: {gm_notes[:200]}")
        self.logger.debug(f"   Player choice: {player_choice}")
        self.logger.debug(f"   Combined text: {combined_text[:400]}")

        try:
            response = self.llm.run(
                messages=[
                    ChatMessage.from_system(system_prompt),
                    ChatMessage.from_user(user_prompt)
                ]
            )

            # Parse JSON from response
            content = response['replies'][0].text.strip()

            self.logger.info(f"   LLM response length: {len(content)} chars")
            self.logger.debug(f"   LLM response: {content[:500]}")

            # Handle markdown code blocks if present
            if content.startswith('```'):
                self.logger.debug("   Removing markdown code block formatting...")
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            enemies = json.loads(content)

            if not isinstance(enemies, list):
                self.logger.warning("   ⚠️  LLM returned non-list response, using empty list")
                enemies = []

            self.logger.info(f"   ✅ Successfully extracted {len(enemies)} enemy types")
            if enemies:
                for i, enemy in enumerate(enemies, 1):
                    self.logger.info(f"      {i}. {enemy.get('name', 'Unknown')} x{enemy.get('count', 1)} (CR {enemy.get('estimated_cr', '?')})")
            else:
                self.logger.warning("   ⚠️  No enemies found in scenario text!")
                self.logger.warning(f"   Scenario scene was: '{scenario.get('scene', 'EMPTY')}'")
                self.logger.warning(f"   GM notes were: '{scenario.get('gm_notes', 'EMPTY')}'")

            return enemies

        except json.JSONDecodeError as e:
            self.logger.error(f"   ❌ Failed to parse enemies from LLM response: {e}")
            self.logger.error(f"   Raw LLM response: {content if 'content' in locals() else 'N/A'}")
            return []
        except Exception as e:
            self.logger.error(f"   ❌ Failed to extract enemies from scenario: {e}")
            self.logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            self.logger.error(f"   Traceback: {traceback.format_exc()}")
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

            # CLAMP THE CR TO WHAT THE PARTY CAN SURVIVE.
            #
            # estimated_cr comes from the scene-extraction LLM, which reads
            # "Voidbringers" and guesses — in a live run it returned CR 3 x3
            # against a LEVEL 1 party, i.e. three 65 HP / AC 16 soldiers versus
            # one character with 8 max HP. party_level was passed to the stat
            # generator as advisory context only, and nothing enforced it, so
            # the encounter was unwinnable by construction.
            requested_cr = enemy.get('estimated_cr', 0.5)
            balanced_cr = self._balanced_cr(requested_cr, party_level, count)
            if balanced_cr != requested_cr:
                self.logger.info(
                    f"      ⚖️ CR {requested_cr} -> {balanced_cr} for a level "
                    f"{party_level} party facing {count} enem"
                    f"{'y' if count == 1 else 'ies'}")
            enemy['estimated_cr'] = balanced_cr

            # Generate stats once (use template if available)
            try:
                npc_stats = self.npc_generator.generate_npc_stats(
                    npc_description=enemy.get('description', enemy_name),
                    challenge_rating=balanced_cr,
                    role=enemy.get('role', 'combatant'),
                    context={
                        'party_level': party_level,
                        'enemy_count': count,
                        'keywords': enemy.get('keywords', [])
                    }
                )

                # LOG GENERATED NPC STATS
                self.logger.info(f"      📊 Generated stats for '{enemy_name}':")
                self.logger.info(f"         Name: {npc_stats.get('name')}")
                self.logger.info(f"         Level: {npc_stats.get('level')}")
                self.logger.info(f"         HP: {npc_stats.get('hit_points')}")
                self.logger.info(f"         Ability Scores: {npc_stats.get('ability_scores')}")

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

        # No need to import RollType since we're using simple d20 rolls
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
                    # Get DEX modifier from entity's ability_scores block
                    dex_mod = entity.ability_scores.get_modifier_from_name("dexterity")

                    # Roll d20 + DEX mod for initiative
                    # Simple roll without using entity.roll_d20 (which expects ModifiableValue)
                    initiative = self._roll_d20() + dex_mod

                initiative_rolls.append({
                    "char_id": char_id,
                    "initiative": initiative
                })

                self.logger.debug(f"      {char_id} initiative: {initiative} (d20 + {dex_mod})")

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

        self.logger.info("📊 INITIALIZING COMBATANT STATES:")

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

            # LOG EACH COMBATANT STATE
            self.logger.info(f"   {char_id}:")
            self.logger.info(f"      Name: {char.name}")
            self.logger.info(f"      HP from CharacterManager: {hp_data}")
            self.logger.info(f"      Initial hp_current: {hp_current}")
            self.logger.info(f"      Initial hp_max: {hp_max}")
            self.logger.info(f"      Is Hostile: {is_npc}")

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

    # Difficulty multipliers applied to the per-enemy CR budget. "medium" is
    # the DMG baseline: a single enemy of CR ~= party level is a fair fight.
    _DIFFICULTY_SCALE = {
        "easy": 0.5,
        "medium": 1.0,
        "hard": 1.5,
        "deadly": 2.0,
    }

    def _balanced_cr(self, requested_cr: float, party_level: int,
                     count: int) -> float:
        """
        Clamp a requested CR to something the party can actually fight.

        The LLM proposes; this decides — the same split the DM tools use for
        rules and dice. Budget: one enemy of CR ~= party level is a fair fight at
        medium, and facing several at once divides the share of each.

        Never raises the CR: if the story calls for something weak, it stays
        weak. This only prevents the unwinnable case.
        """
        try:
            requested = float(requested_cr)
        except (TypeError, ValueError):
            requested = 0.5

        level = max(1, int(party_level or 1))
        scale = self._DIFFICULTY_SCALE.get(self._difficulty(), 1.0)
        enemies = max(1, int(count or 1))

        # Total budget for the encounter, shared across the enemies present.
        ceiling = (level * scale) / enemies
        # A floor so a level 1 party still meets something with stats.
        ceiling = max(0.125, ceiling)

        return round(min(requested, ceiling), 3)

    def _difficulty(self) -> str:
        """The campaign's difficulty, lowercased; 'medium' if unknown."""
        for source in (getattr(self.game_engine, "campaign_config", None),
                       self.game_engine):
            value = getattr(source, "difficulty", None)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return "medium"

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
