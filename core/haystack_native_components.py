"""
Native Haystack Components for D&D Assistant
Phase 3: Convert all agents to pure Haystack components
"""

import os
import random
import time
import json
from typing import Dict, Any, List, Optional, Union
from haystack import component
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
# from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
# from haystack.components.embedders import SentenceTransformersTextEmbedder
# from haystack.components.builders import PromptBuilder, AnswerBuilder
# from haystack.components.rankers import SentenceTransformersSimilarityRanker

# Import event sourcing from enhanced game engine
from core.enhanced_game_engine import GameEvent, EventStore, StateProjector

# Configuration constants from haystack_pipeline_agent
DEFAULT_EMBEDDING_DIM = 384
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

@component
class CharacterDataComponent:
    """Unified character data management using Haystack"""
    
    def __init__(self,
                 characters_dir: str = "docs/characters",
                 collection_name: str = "dnd_characters",
                 verbose: bool = False):
        self.characters_dir = characters_dir
        self.collection_name = collection_name
        self.verbose = verbose
        
        # Character data storage
        self.characters = {}
        self.character_store = self._setup_character_store()
        
        # Load existing character data
        self._load_character_data()
        
        if verbose:
            print(f"👥 CharacterDataComponent initialized with {len(self.characters)} characters")
    
    def _setup_character_store(self) -> Optional[QdrantDocumentStore]:
        """Setup Qdrant document store for character data"""
        try:
            # Initialize local document store for characters
            character_store = QdrantDocumentStore(
                path="../qdrant_storage",
                index=self.collection_name,
                embedding_dim=DEFAULT_EMBEDDING_DIM
            )
            
            if self.verbose:
                print(f"✓ Connected to local Qdrant storage for characters: {self.collection_name}")
            return character_store
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Local Qdrant storage not available for characters, using fallback: {e}")
            # Don't raise error, just disable document store for graceful degradation
            return None
    
    def _load_character_data(self):
        """Load character data from files"""
        import os
        
        if not os.path.exists(self.characters_dir):
            return
        
        for filename in os.listdir(self.characters_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.characters_dir, filename), 'r') as f:
                        char_data = json.load(f)
                        char_name = char_data.get('name', filename.replace('.json', ''))
                        self.characters[char_name] = char_data
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Failed to load character {filename}: {e}")
    
    @component.output_types(
        character_data=Dict[str, Any],
        modifiers=Dict[str, Any],
        proficiencies=Dict[str, Any],
        conditions=List[str],
        success=bool
    )
    def run(self, character_name: str, request_type: str = "full_data") -> Dict[str, Any]:
        """Get character data"""
        
        if character_name not in self.characters:
            # Create basic character template
            char_data = self._create_default_character(character_name)
            self.characters[character_name] = char_data
        else:
            char_data = self.characters[character_name]
        
        # Extract specific data based on request type
        if request_type == "modifiers":
            modifiers = self._calculate_modifiers(char_data)
        else:
            modifiers = self._get_all_modifiers(char_data)
        
        proficiencies = char_data.get("proficiencies", {})
        conditions = char_data.get("conditions", [])
        
        return {
            "character_data": char_data,
            "modifiers": modifiers,
            "proficiencies": proficiencies, 
            "conditions": conditions,
            "success": True
        }
    
    def _create_default_character(self, name: str) -> Dict[str, Any]:
        """Create a default character template"""
        return {
            "name": name,
            "class": "Fighter",
            "level": 1,
            "abilities": {
                "strength": 15,
                "dexterity": 14,
                "constitution": 13,
                "intelligence": 12,
                "wisdom": 10,
                "charisma": 8
            },
            "proficiencies": {
                "athletics": True,
                "intimidation": True
            },
            "conditions": [],
            "hp": {"current": 12, "max": 12}
        }
    
    def _calculate_modifiers(self, char_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate ability modifiers"""
        abilities = char_data.get("abilities", {})
        modifiers = {}
        
        for ability, score in abilities.items():
            modifiers[ability] = (score - 10) // 2
        
        return modifiers
    
    def _get_all_modifiers(self, char_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get all modifiers including skills"""
        base_modifiers = self._calculate_modifiers(char_data)
        skill_modifiers = {}
        
        # Calculate skill modifiers
        skill_ability_map = {
            "athletics": "strength",
            "acrobatics": "dexterity", 
            "stealth": "dexterity",
            "perception": "wisdom",
            "investigation": "intelligence",
            "insight": "wisdom",
            "persuasion": "charisma",
            "deception": "charisma",
            "intimidation": "charisma"
        }
        
        proficiencies = char_data.get("proficiencies", {})
        level = char_data.get("level", 1)
        prof_bonus = 2 + ((level - 1) // 4)  # Standard proficiency bonus
        
        for skill, ability in skill_ability_map.items():
            base_mod = base_modifiers.get(ability, 0)
            if proficiencies.get(skill, False):
                skill_modifiers[skill] = base_mod + prof_bonus
            else:
                skill_modifiers[skill] = base_mod
        
        return {
            "ability_modifiers": base_modifiers,
            "skill_modifiers": skill_modifiers,
            "proficiency_bonus": prof_bonus
        }


@component
class CampaignContextComponent:
    """Campaign and world state management"""
    
    def __init__(self, campaigns_dir: str = "resources/current_campaign", verbose: bool = False):
        self.campaigns_dir = campaigns_dir
        self.verbose = verbose
        
        # Campaign data storage
        self.campaign_data = {}
        self.world_state = {}
        
        # Load campaign data
        self._load_campaign_data()
        
        if verbose:
            print(f"🌍 CampaignContextComponent initialized")
    
    def _load_campaign_data(self):
        """Load campaign data from files"""
        import os
        
        if not os.path.exists(self.campaigns_dir):
            return
        
        # Load campaign info
        info_file = os.path.join(self.campaigns_dir, "campaign_info.json")
        if os.path.exists(info_file):
            try:
                with open(info_file, 'r') as f:
                    self.campaign_data = json.load(f)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to load campaign info: {e}")
        
        # Load world state
        world_file = os.path.join(self.campaigns_dir, "world_state.json") 
        if os.path.exists(world_file):
            try:
                with open(world_file, 'r') as f:
                    self.world_state = json.load(f)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to load world state: {e}")
    
    @component.output_types(
        campaign_info=Dict[str, Any],
        world_state=Dict[str, Any],
        location_info=Dict[str, Any],
        success=bool
    )
    def run(self, query_type: str = "full", location: str = None) -> Dict[str, Any]:
        """Get campaign context information"""
        
        # Get location-specific info if requested
        location_info = {}
        if location:
            location_info = self.world_state.get("locations", {}).get(location, {})
        
        return {
            "campaign_info": self.campaign_data,
            "world_state": self.world_state,
            "location_info": location_info,
            "success": True
        }


@component
class RuleEnforcementComponent:
    """D&D rules validation and enforcement"""
    
    def __init__(self, strict_mode: bool = False, verbose: bool = False):
        self.strict_mode = strict_mode
        self.verbose = verbose
        
        # Rules database (simplified)
        self.rules_db = self._initialize_rules_db()
        
        if verbose:
            print(f"📜 RuleEnforcementComponent initialized (strict: {strict_mode})")
    
    def _initialize_rules_db(self) -> Dict[str, Any]:
        """Initialize basic rules database"""
        return {
            "skills": {
                "athletics": {"ability": "strength", "untrained": True},
                "acrobatics": {"ability": "dexterity", "untrained": True},
                "stealth": {"ability": "dexterity", "untrained": True},
                "perception": {"ability": "wisdom", "untrained": True},
                "investigation": {"ability": "intelligence", "untrained": True},
                "insight": {"ability": "wisdom", "untrained": True},
                "persuasion": {"ability": "charisma", "untrained": True},
                "deception": {"ability": "charisma", "untrained": True},
                "intimidation": {"ability": "charisma", "untrained": True}
            },
            "difficulty_classes": {
                "trivial": 5,
                "easy": 10,
                "medium": 15,
                "hard": 20,
                "very_hard": 25,
                "nearly_impossible": 30
            },
            "conditions": {
                "advantage": "Roll twice, take higher",
                "disadvantage": "Roll twice, take lower",
                "blessed": "Add 1d4 to rolls",
                "cursed": "Subtract 1d4 from rolls"
            }
        }
    
    @component.output_types(
        validation_result=Dict[str, Any],
        requires_check=bool,
        skill=Optional[str],
        dc=Optional[int],
        success=bool
    )
    def run(self,
            action: str = None,
            context: Dict[str, Any] = None,
            character_data: Dict[str, Any] = None,
            modifiers: Dict[str, Any] = None,
            proficiencies: Dict[str, Any] = None,
            conditions: List[str] = None) -> Dict[str, Any]:
        """Validate and determine requirements for an action"""
        
        context = context or {}
        
        # If we received character data from previous component, use it
        if character_data:
            context["character_data"] = character_data
        if modifiers:
            context["modifiers"] = modifiers
        if proficiencies:
            context["proficiencies"] = proficiencies
        if conditions:
            context["conditions"] = conditions
        
        # Get action from context if not provided directly
        if not action:
            action = context.get("action", "unknown action")
        
        # Parse the action to determine what type of check is needed
        check_info = self._analyze_action(action, context)
        
        # Validate the requested action
        validation = self._validate_action(check_info)
        
        return {
            "validation_result": validation,
            "requires_check": check_info["requires_check"],
            "skill": check_info.get("skill"),
            "dc": check_info.get("dc"),
            "success": validation.get("valid", True)
        }
    
    def _analyze_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze action to determine check requirements"""
        
        action_lower = action.lower()
        
        # Check for skill-specific actions
        for skill in self.rules_db["skills"]:
            if skill in action_lower:
                return {
                    "type": "skill_check",
                    "skill": skill,
                    "requires_check": True,
                    "dc": self._determine_dc(action, context)
                }
        
        # Check for common action keywords
        if any(word in action_lower for word in ["climb", "jump", "swim"]):
            return {
                "type": "skill_check",
                "skill": "athletics",
                "requires_check": True,
                "dc": self._determine_dc(action, context)
            }
        
        if any(word in action_lower for word in ["hide", "sneak"]):
            return {
                "type": "skill_check", 
                "skill": "stealth",
                "requires_check": True,
                "dc": self._determine_dc(action, context)
            }
        
        if any(word in action_lower for word in ["look", "search", "spot"]):
            return {
                "type": "skill_check",
                "skill": "perception", 
                "requires_check": True,
                "dc": self._determine_dc(action, context)
            }
        
        # Default to no check required
        return {
            "type": "free_action",
            "requires_check": False
        }
    
    def _determine_dc(self, action: str, context: Dict[str, Any]) -> int:
        """Determine appropriate DC for an action"""
        
        # Check context for explicit difficulty
        difficulty = context.get("difficulty", "medium")
        
        if difficulty in self.rules_db["difficulty_classes"]:
            return self.rules_db["difficulty_classes"][difficulty]
        
        # Check context for explicit DC
        if "dc" in context:
            return context["dc"]
        
        # Analyze action text for difficulty indicators
        action_lower = action.lower()
        
        if any(word in action_lower for word in ["easy", "simple", "basic"]):
            return 10
        elif any(word in action_lower for word in ["hard", "difficult", "challenging"]):
            return 20
        elif any(word in action_lower for word in ["impossible", "extreme"]):
            return 25
        
        # Default DC
        return 15
    
    def _validate_action(self, check_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the action according to rules"""
        
        if not self.strict_mode:
            # In non-strict mode, allow most actions
            return {"valid": True, "message": "Action allowed"}
        
        # In strict mode, perform more rigorous validation
        action_type = check_info.get("type", "unknown")
        
        if action_type == "skill_check":
            skill = check_info.get("skill")
            if skill not in self.rules_db["skills"]:
                return {
                    "valid": False,
                    "error": f"Unknown skill: {skill}",
                    "message": "Invalid skill specified"
                }
        
        return {"valid": True, "message": "Action validated"}


@component
class DiceSystemComponent:
    """Dice rolling and probability calculations"""
    
    def __init__(self, seed: int = None, verbose: bool = False):
        self.verbose = verbose
        
        # Initialize random number generator
        if seed:
            random.seed(seed)
        
        # Dice roll history for session
        self.roll_history = []
        
        if verbose:
            print(f"🎲 DiceSystemComponent initialized")
    
    @component.output_types(
        roll_result=Dict[str, Any],
        total=int,
        breakdown=List[int],
        success=bool
    )
    def run(self,
            expression: str = "1d20",
            advantage: bool = False,
            disadvantage: bool = False,
            modifier: int = 0,
            context: Dict[str, Any] = None,
            skill: Optional[str] = None,
            dc: Optional[int] = None) -> Dict[str, Any]:
        """Execute dice roll with modifiers"""
        
        try:
            # If we received context from rule validation, use it to determine roll parameters
            if context and "modifiers" in context and skill:
                skill_modifiers = context["modifiers"].get("skill_modifiers", {})
                modifier = skill_modifiers.get(skill, 0)
                expression = "1d20"  # Standard skill check
            
            # Parse dice expression
            dice_info = self._parse_dice_expression(expression)
            
            # Handle advantage/disadvantage
            if advantage and not disadvantage:
                dice_info["count"] = max(2, dice_info["count"])
                dice_info["keep_highest"] = True
            elif disadvantage and not advantage:
                dice_info["count"] = max(2, dice_info["count"])
                dice_info["keep_lowest"] = True
            
            # Roll dice
            rolls = []
            for _ in range(dice_info["count"]):
                roll = random.randint(1, dice_info["sides"])
                rolls.append(roll)
            
            # Apply advantage/disadvantage
            if dice_info.get("keep_highest"):
                final_roll = max(rolls)
                breakdown = [f"({', '.join(map(str, rolls))}, keep highest: {final_roll})"]
            elif dice_info.get("keep_lowest"):
                final_roll = min(rolls)
                breakdown = [f"({', '.join(map(str, rolls))}, keep lowest: {final_roll})"]
            else:
                final_roll = sum(rolls)
                breakdown = rolls
            
            # Apply modifier
            total = final_roll + modifier + dice_info.get("base_modifier", 0)
            
            # Create result
            result = {
                "expression": expression,
                "rolls": rolls,
                "final_roll": final_roll,
                "modifier": modifier,
                "total": total,
                "advantage": advantage,
                "disadvantage": disadvantage,
                "timestamp": time.time()
            }
            
            # Store in history
            self.roll_history.append(result)
            
            if self.verbose:
                print(f"🎲 Rolled {expression}: {total}")
            
            return {
                "roll_result": result,
                "total": total,
                "breakdown": breakdown,
                "success": True
            }
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Dice roll failed: {e}")
            
            return {
                "roll_result": {"error": str(e)},
                "total": 0,
                "breakdown": [],
                "success": False
            }
    
    def _parse_dice_expression(self, expr: str) -> Dict[str, Any]:
        """Parse dice expression like '2d20+5'"""
        
        # Simple parser for basic dice expressions
        expr = expr.lower().replace(" ", "")
        
        # Default values
        count = 1
        sides = 20
        modifier = 0
        
        # Parse modifier
        if "+" in expr:
            parts = expr.split("+")
            expr = parts[0]
            modifier = int(parts[1]) if parts[1].isdigit() else 0
        elif "-" in expr and expr.count("-") == 1:
            parts = expr.split("-")
            expr = parts[0]
            modifier = -int(parts[1]) if parts[1].isdigit() else 0
        
        # Parse dice
        if "d" in expr:
            dice_parts = expr.split("d")
            if dice_parts[0]:
                count = int(dice_parts[0])
            if dice_parts[1]:
                sides = int(dice_parts[1])
        else:
            # Just a number
            if expr.isdigit():
                modifier = int(expr)
                count = 0
                sides = 0
        
        return {
            "count": count,
            "sides": sides, 
            "base_modifier": modifier
        }


@component
class CombatEngineComponent:
    """Combat mechanics and initiative tracking"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # Combat state
        self.combat_active = False
        self.initiative_order = []
        self.current_turn = 0
        self.round_number = 0
        
        # Combat participants
        self.participants = {}
        
        if verbose:
            print(f"⚔️ CombatEngineComponent initialized")
    
    @component.output_types(
        combat_result=Dict[str, Any],
        initiative_order=List[Dict[str, Any]],
        combat_active=bool,
        success=bool
    )
    def run(self, 
            action: str,
            actor: str,
            target: str = None,
            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process combat action"""
        
        context = context or {}
        
        # Handle different combat actions
        if action.lower() == "start_combat":
            return self._start_combat(context)
        elif action.lower() == "end_combat":
            return self._end_combat()
        elif action.lower() == "next_turn":
            return self._next_turn()
        elif action.lower() in ["attack", "spell_attack"]:
            return self._process_attack(actor, target, context)
        else:
            return self._process_generic_action(actor, action, context)
    
    def _start_combat(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Start combat and roll initiative"""
        
        participants = context.get("participants", [])
        
        self.combat_active = True
        self.round_number = 1
        self.current_turn = 0
        self.participants = {}
        
        # Roll initiative for all participants
        initiative_rolls = []
        for participant in participants:
            name = participant.get("name", "Unknown")
            init_bonus = participant.get("initiative_bonus", 0)
            
            # Roll d20 + initiative bonus
            roll = random.randint(1, 20) + init_bonus
            
            initiative_rolls.append({
                "name": name,
                "initiative": roll,
                "participant_data": participant
            })
            
            self.participants[name] = participant
        
        # Sort by initiative (highest first)
        self.initiative_order = sorted(initiative_rolls, key=lambda x: x["initiative"], reverse=True)
        
        if self.verbose:
            print(f"⚔️ Combat started with {len(participants)} participants")
        
        return {
            "combat_result": {
                "action": "combat_started",
                "message": f"Combat started! Round {self.round_number}"
            },
            "initiative_order": self.initiative_order,
            "combat_active": True,
            "success": True
        }
    
    def _end_combat(self) -> Dict[str, Any]:
        """End combat"""
        
        self.combat_active = False
        self.initiative_order = []
        self.current_turn = 0
        self.round_number = 0
        self.participants = {}
        
        if self.verbose:
            print("⚔️ Combat ended")
        
        return {
            "combat_result": {
                "action": "combat_ended",
                "message": "Combat has ended"
            },
            "initiative_order": [],
            "combat_active": False,
            "success": True
        }
    
    def _next_turn(self) -> Dict[str, Any]:
        """Advance to next turn"""
        
        if not self.combat_active:
            return {
                "combat_result": {"error": "No active combat"},
                "initiative_order": [],
                "combat_active": False,
                "success": False
            }
        
        self.current_turn += 1
        if self.current_turn >= len(self.initiative_order):
            self.current_turn = 0
            self.round_number += 1
        
        current_participant = self.initiative_order[self.current_turn]
        
        return {
            "combat_result": {
                "action": "turn_advanced",
                "current_actor": current_participant["name"],
                "round": self.round_number,
                "message": f"It's {current_participant['name']}'s turn (Round {self.round_number})"
            },
            "initiative_order": self.initiative_order,
            "combat_active": True,
            "success": True
        }
    
    def _process_attack(self, actor: str, target: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process an attack action"""
        
        # Simplified attack resolution
        attack_roll = random.randint(1, 20)
        attack_bonus = context.get("attack_bonus", 5)
        total_attack = attack_roll + attack_bonus
        
        target_ac = context.get("target_ac", 15)
        hit = total_attack >= target_ac
        
        damage = 0
        if hit:
            damage_dice = context.get("damage_dice", "1d8")
            damage_bonus = context.get("damage_bonus", 3)
            damage_roll = random.randint(1, 8)  # Simplified
            damage = damage_roll + damage_bonus
        
        result_message = f"{actor} attacks {target}: {total_attack} vs AC {target_ac}"
        if hit:
            result_message += f" - Hit! {damage} damage"
        else:
            result_message += " - Miss!"
        
        return {
            "combat_result": {
                "action": "attack",
                "actor": actor,
                "target": target,
                "attack_roll": attack_roll,
                "total_attack": total_attack,
                "hit": hit,
                "damage": damage,
                "message": result_message
            },
            "initiative_order": self.initiative_order,
            "combat_active": self.combat_active,
            "success": True
        }
    
    def _process_generic_action(self, actor: str, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a generic combat action"""
        
        return {
            "combat_result": {
                "action": action,
                "actor": actor,
                "message": f"{actor} performs {action}"
            },
            "initiative_order": self.initiative_order,
            "combat_active": self.combat_active,
            "success": True
        }


@component
class GameStateComponent:
    """Centralized game state using event sourcing"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # Event sourcing components
        self.event_store = EventStore()
        self.state_projector = StateProjector()
        
        # Current state cache
        self.current_state = {
            "characters": {},
            "campaign": {},
            "session": {"active": False},
            "combat": {"active": False},
            "world_state": {}
        }
        
        if verbose:
            print("🎮 GameStateComponent initialized with event sourcing")
    
    @component.output_types(
        updated_state=Dict[str, Any],
        event_id=str,
        success=bool
    )
    def run(self,
            event_type: str = None,
            actor: str = None,
            payload: Dict[str, Any] = None,
            context: Dict[str, Any] = None,
            final_result: Dict[str, Any] = None,
            success: bool = None) -> Dict[str, Any]:
        """Apply event to game state"""
        
        try:
            # If we received final_result from result calculator, convert it to event format
            if final_result and not event_type:
                event_type = "skill_check_result"
                actor = context.get("character_name", "unknown") if context else "unknown"
                payload = final_result
            
            # Ensure we have required event information
            if not event_type:
                event_type = "generic_event"
            if not actor:
                actor = "system"
            if not payload:
                payload = final_result or {}
            
            # Create game event
            event = GameEvent(
                event_id=f"{event_type}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                event_type=event_type,
                actor=actor,
                payload=payload
            )
            
            # Append to event store
            self.event_store.append_event(event)
            
            # Project current state with proper signature
            projected_state = self.state_projector.project_state(self.event_store.events, self.current_state)
            
            # Update cached state
            self.current_state.update(projected_state)
            
            if self.verbose:
                print(f"🎮 Applied event: {event_type} by {actor}")
            
            return {
                "updated_state": projected_state,
                "event_id": event.event_id,
                "success": True
            }
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to apply event: {e}")
            
            return {
                "updated_state": {},
                "event_id": "",
                "success": False
            }