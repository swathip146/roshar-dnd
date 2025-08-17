"""
Manual Command Handler for Modular DM Assistant

This handler uses explicit command mapping and pattern matching to determine
user intent and route commands to appropriate agents.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional
from .base_command_handler import BaseCommandHandler

# Configuration constants
MAX_TIMEOUT = 40

class ManualCommandHandler(BaseCommandHandler):
    """
    Manual command handler that uses explicit command mapping and pattern matching.
    
    This implementation provides deterministic command processing through
    predefined command patterns and manual routing logic.
    """
    
    def __init__(self, dm_assistant):
        """Initialize the manual command handler."""
        super().__init__(dm_assistant)
        
        # Initialize command mapping
        self.command_map = {
            # Campaign management
            'list campaigns': ('campaign_manager', 'list_campaigns'),
            'show campaigns': ('campaign_manager', 'list_campaigns'),
            'available campaigns': ('campaign_manager', 'list_campaigns'),
            'select campaign': ('campaign_manager', 'select_campaign'),
            'choose campaign': ('campaign_manager', 'select_campaign'),
            'campaign info': ('campaign_manager', 'get_campaign_info'),
            'show campaign': ('campaign_manager', 'get_campaign_info'),
            'current campaign': ('campaign_manager', 'get_campaign_info'),
            
            # Player management
            'list players': ('campaign_manager', 'list_players'),
            'show players': ('campaign_manager', 'list_players'),
            'party members': ('campaign_manager', 'list_players'),
            'player info': ('campaign_manager', 'get_player_info'),
            'show player': ('campaign_manager', 'get_player_info'),
            
            # Dice rolling
            'roll': ('dice_system', 'roll_dice'),
            'dice': ('dice_system', 'roll_dice'),
            
            # Combat commands
            'start combat': ('combat_engine', 'start_combat'),
            'begin combat': ('combat_engine', 'start_combat'),
            'initiative': ('combat_engine', 'start_combat'),
            'combat status': ('combat_engine', 'get_combat_status'),
            'initiative order': ('combat_engine', 'get_combat_status'),
            'next turn': ('combat_engine', 'next_turn'),
            'end turn': ('combat_engine', 'next_turn'),
            'advance turn': ('combat_engine', 'next_turn'),
            'end combat': ('combat_engine', 'end_combat'),
            'stop combat': ('combat_engine', 'end_combat'),
            
            # Combat System Enhancements (Phase 2)
            'cast spell': ('combat_engine', 'cast_spell'),
            'apply damage': ('combat_engine', 'apply_damage'),
            'apply healing': ('combat_engine', 'apply_healing'),
            'add condition': ('combat_engine', 'add_condition'),
            'remove condition': ('combat_engine', 'remove_condition'),
            
            # Rule queries
            'rule': ('rule_enforcement', 'check_rule'),
            'check rule': ('rule_enforcement', 'check_rule'),
            'how does': ('rule_enforcement', 'check_rule'),
            'what happens': ('rule_enforcement', 'check_rule'),
            
            # Scenario generation - Updated to use RAG-first refactored generator
            'introduce scenario': ('scenario_generator', 'generate_scenario'),
            'generate scenario': ('scenario_generator', 'generate_scenario'),
            'create scenario': ('scenario_generator', 'generate_scenario'),
            'new scene': ('scenario_generator', 'generate_scenario'),
            'encounter': ('scenario_generator', 'generate_scenario'),
            'adventure': ('scenario_generator', 'generate_scenario'),
            # Removed 'select option' entries - handled by regex in _parse_command
            
            # Game state management
            'save game': ('game_engine', 'save_game'),
            'load game': ('game_engine', 'load_game'),
            'list saves': ('game_engine', 'list_saves'),
            'load save': ('game_engine', 'load_save'),
            'game state': ('game_engine', 'get_game_state'),
            
            # System commands
            'agent status': ('orchestrator', 'get_agent_status'),
            'system status': ('orchestrator', 'get_agent_status'),
            
            # Character management
            'create character': ('character_manager', 'create_character'),
            'new character': ('character_manager', 'create_character'),
            'level up': ('experience_manager', 'level_up'),
            
            # Character Management Extensions (Phase 2)
            'update character': ('character_manager', 'update_character'),
            'roll ability scores': ('character_manager', 'roll_ability_scores'),
            'calculate modifier': ('character_manager', 'calculate_modifier'),
            'update ability scores': ('character_manager', 'update_ability_scores'),
            
            # Rest mechanics
            'short rest': ('session_manager', 'take_short_rest'),
            'long rest': ('session_manager', 'take_long_rest'),
            'sleep': ('session_manager', 'take_long_rest'),
            
            # Session Management Extensions (Phase 2)
            'advance time': ('session_manager', 'advance_time'),
            'check rest eligibility': ('session_manager', 'check_rest_eligibility'),
            'get session info': ('session_manager', 'get_session_info'),
            
            # Inventory management
            'add item': ('inventory_manager', 'add_item'),
            'remove item': ('inventory_manager', 'remove_item'),
            'show inventory': ('inventory_manager', 'get_inventory'),
            'list items': ('inventory_manager', 'get_inventory'),
            
            # Inventory Management Extensions (Phase 2)
            'search items': ('inventory_manager', 'search_items'),
            'get item info': ('inventory_manager', 'get_item_info'),
            'transfer item': ('inventory_manager', 'transfer_item'),
            'get armor class': ('inventory_manager', 'get_armor_class'),
            'initialize inventory': ('inventory_manager', 'initialize_inventory'),
            
            # Spell management
            'cast spell': ('spell_manager', 'cast_spell'),
            'cast': ('spell_manager', 'cast_spell'),
            'prepare spells': ('spell_manager', 'get_prepared_spells'),
            
            # NPC interaction commands
            'talk to npc': ('npc_controller', 'generate_npc_dialogue'),
            'npc dialogue': ('npc_controller', 'generate_npc_dialogue'),
            'speak to': ('npc_controller', 'generate_npc_dialogue'),
            'npc behavior': ('npc_controller', 'generate_npc_behavior'),
            'npc status': ('npc_controller', 'get_npc_state'),
            'update npc': ('npc_controller', 'update_npc_stats'),
            'npc interaction': ('npc_controller', 'npc_social_interaction'),
            'persuade': ('npc_controller', 'npc_social_interaction'),
            'intimidate': ('npc_controller', 'npc_social_interaction'),
            'deceive': ('npc_controller', 'npc_social_interaction'),
            
            # NPC Management Extensions (Phase 2)
            'remove npc': ('npc_controller', 'remove_npc'),
            
            # Experience & Progression (Phase 2)
            'calculate encounter xp': ('experience_manager', 'calculate_encounter_xp'),
            'award milestone': ('experience_manager', 'award_milestone'),
            'initialize character xp': ('experience_manager', 'initialize_character_xp'),
            
            # Phase 3: Medium Priority Commands
            
            # Advanced Experience Management (5 commands)
            'get level progression': ('experience_manager', 'get_level_progression'),
            'set milestone progression': ('experience_manager', 'set_milestone_progression'),
            'get xp to next level': ('experience_manager', 'get_xp_to_next_level'),
            'bulk level party': ('experience_manager', 'bulk_level_party'),
            'reset xp': ('experience_manager', 'reset_xp'),
            
            # Advanced Inventory Management (3 commands)
            'calculate carrying capacity': ('inventory_manager', 'calculate_carrying_capacity'),
            'create custom item': ('inventory_manager', 'create_custom_item'),
            'get carrying capacity': ('inventory_manager', 'get_carrying_capacity'),
            
            # Rule Enforcement & Validation (5 commands)
            'validate action': ('rule_enforcement', 'validate_action'),
            'validate spell cast': ('rule_enforcement', 'validate_spell_cast'),
            'validate attack': ('rule_enforcement', 'validate_attack'),
            'validate movement': ('rule_enforcement', 'validate_movement'),
            'get rule summary': ('rule_enforcement', 'get_rule_summary'),
            
            # Advanced Session Management (3 commands)
            'get rest status': ('session_manager', 'get_rest_status'),
            'add time': ('session_manager', 'add_time'),
            'get session status': ('session_manager', 'get_session_status'),
            
            # Knowledge & Information Systems (3 commands)
            'retrieve documents': ('haystack_pipeline', 'retrieve_documents'),
            'query rules': ('haystack_pipeline', 'query_rules'),
            'get pipeline status': ('haystack_pipeline', 'get_pipeline_status'),
            
            # Phase 4: Low Priority Administrative/Advanced Commands
            
            # Game Engine Commands (6 commands)
            'enqueue action': ('game_engine', 'enqueue_action'),
            'get game state': ('game_engine', 'get_game_state'),
            'update game state': ('game_engine', 'update_game_state'),
            'process player action': ('game_engine', 'process_player_action'),
            'should generate scene': ('game_engine', 'should_generate_scene'),
            'add scene to history': ('game_engine', 'add_scene_to_history'),
            
            # Advanced Scenario Generation (3 commands)
            # 'generate scenario advanced': ('scenario_generator', 'generate_scenario'),
            # 'apply player choice advanced': ('scenario_generator', 'apply_player_choice'),
            'get generator status': ('scenario_generator', 'get_generator_status'),
            
            # Advanced NPC Management (3 commands)
            'update npc advanced': ('npc_controller', 'update_npc'),
            'get npc relationships': ('npc_controller', 'get_npc_relationships'),
            'update npc relationship': ('npc_controller', 'update_npc_relationship'),
            
            # Campaign Management Extensions (2 commands)
            'add player to game': ('campaign_manager', 'add_player_to_game'),
            'get campaign context': ('campaign_manager', 'get_campaign_context'),
            
            # Dice System Extensions (3 commands)
            'roll hit points': ('dice_system', 'roll_hit_points'),
            'get roll history': ('dice_system', 'get_roll_history'),
            'clear roll history': ('dice_system', 'clear_roll_history'),
            
            # Advanced Rule & Knowledge (2 commands)
            'validate ability check': ('rule_enforcement', 'validate_ability_check'),
            'get collection info': ('haystack_pipeline', 'get_collection_info')
        }
    
    def handle_command(self, user_command: str) -> str:
        """
        Process user command using manual command mapping and pattern matching.
        
        Args:
            user_command: The raw user input string
            
        Returns:
            str: The response to display to the user
        """
        instruction_lower = user_command.lower().strip()
        
        # Handle help command directly
        if instruction_lower == "help":
            return self._get_command_help()
        
        # Handle numeric input for campaign selection
        if self._is_numeric_selection(instruction_lower):
            return self._handle_numeric_selection(instruction_lower)
        
        # Parse command using command processor
        agent_id, action, params = self._parse_command(user_command)
        
        if agent_id == "help":
            return self._get_command_help()
        elif agent_id and action:
            return self._route_command(agent_id, action, user_command, params)
        
        # Fallback to general query
        return self._handle_general_query(user_command)
    
    def get_supported_commands(self) -> Dict[str, str]:
        """Get a dictionary of supported commands and their descriptions."""
        return {
            # Campaign Management
            "list campaigns": "Show available campaigns",
            "select campaign [number]": "Choose a campaign",
            "campaign info": "Show current campaign details",
            "add player to game [player] [campaign]": "Add player to specific campaign",
            "get campaign context [campaign]": "Get detailed campaign context",
            
            # Player & Character Management
            "list players": "Show all players",
            "player info [name]": "Show player details",
            "create character [name]": "Create new character",
            "update character [name] [field] [value]": "Update character attribute",
            "roll ability scores [method]": "Roll ability scores using specified method",
            "calculate modifier [score]": "Calculate ability modifier for score",
            "update ability scores [character] [scores]": "Update character ability scores",
            
            # Combat System
            "start combat": "Begin combat encounter",
            "combat status": "Show initiative order",
            "next turn": "Advance to next combatant",
            "end combat": "Finish combat encounter",
            "cast spell [spell] [level] [target]": "Cast spell in combat",
            "apply damage [target] [amount] [type]": "Apply damage to target",
            "apply healing [target] [amount]": "Apply healing to target",
            "add condition [target] [condition] [duration]": "Add status condition",
            "remove condition [target] [condition]": "Remove status condition",
            
            # Experience & Progression
            "level up [character]": "Level up character",
            "calculate encounter xp [monsters] [party_size]": "Calculate XP for encounter",
            "award milestone [character] [description]": "Award milestone XP",
            "initialize character xp [character] [level]": "Initialize XP tracking",
            "get level progression [character]": "Show character level progression",
            "set milestone progression [character]": "Enable milestone leveling",
            "get xp to next level [character]": "Show XP needed for next level",
            "bulk level party [characters] [levels]": "Level up multiple characters",
            "reset xp [character] [level]": "Reset character XP to level",
            
            # Inventory & Items
            "show inventory [character]": "Display character items",
            "add item [item] [character]": "Add item to inventory",
            "remove item [item] [character]": "Remove item from inventory",
            "search items [query] [type]": "Search for specific items",
            "get item info [item]": "Get detailed item information",
            "transfer item [from] [to] [item]": "Transfer item between characters",
            "get armor class [character]": "Calculate character AC",
            "initialize inventory [character] [strength]": "Set up character inventory",
            "calculate carrying capacity [strength]": "Calculate carrying capacity",
            "create custom item [description]": "Create custom item",
            "get carrying capacity [character]": "Check character encumbrance",
            
            # Session Management & Time
            "short rest": "Take a short rest",
            "long rest": "Take a long rest",
            "advance time [amount] [unit]": "Advance game time",
            "check rest eligibility [players]": "Check who can rest",
            "get session info": "Show current session details",
            "get rest status [character]": "Check character rest status",
            "add time [hours] [minutes] [activity]": "Add time with activity",
            "get session status": "Show comprehensive session status",
            
            # NPC Management
            "talk to npc [name] [message]": "Generate NPC dialogue",
            "npc dialogue [name]": "Generate NPC conversation",
            "npc behavior [context]": "Generate NPC behavior",
            "npc status [name]": "Show NPC status and stats",
            "update npc [name]": "Update NPC information",
            "remove npc [name]": "Remove NPC from game",
            "update npc advanced [name] [field] [value]": "Advanced NPC update",
            "get npc relationships [name]": "Show NPC relationships",
            "update npc relationship [npc1] [npc2] [value]": "Update NPC relationship",
            
            # Rule Enforcement & Validation
            "rule [topic]": "Look up D&D rules",
            "validate action [action]": "Validate game action legality",
            "validate spell cast [spell_data]": "Validate spell casting",
            "validate attack [attack_data]": "Validate attack action",
            "validate movement [movement_data]": "Validate movement action",
            "get rule summary [topic]": "Get rule summary for topic",
            "validate ability check [check_data]": "Validate ability check",
            
            # Dice System
            "roll [dice]": "Roll dice (e.g., 'roll 1d20', 'roll 3d6+2')",
            "roll hit points [die] [level] [con_mod]": "Roll hit points for level",
            "get roll history [limit]": "Show recent dice roll history",
            "clear roll history": "Clear dice roll history",
            
            # Scenarios & Stories
            "generate scenario": "Create new story scenario",
            "select option [number]": "Choose story option",
            "generate scenario advanced [state]": "Advanced scenario generation",
            "apply player choice advanced [state] [player] [choice]": "Process advanced player choice",
            "get generator status": "Show scenario generator status",
            
            # Knowledge & Information System
            "retrieve documents [query] [max_docs]": "Search knowledge base",
            "query rules [rule_query]": "Query rule database",
            "get pipeline status": "Show knowledge pipeline status",
            "get collection info": "Show knowledge collection information",
            
            # Game Engine & State
            "save game [name]": "Save current game state",
            "load game [name]": "Load saved game state",
            "list saves": "Show available save files",
            "enqueue action [action]": "Queue game action for processing",
            "get game state": "Show current game state",
            "update game state [updates]": "Update game state",
            "process player action [action]": "Process player action",
            "should generate scene": "Check if new scene should be generated",
            "add scene to history [scene]": "Add scene to game history",
            
            # System Management
            "agent status": "Show system agent status",
            "system status": "Show comprehensive system status",
            "help": "Show this help message"
        }
    
    def _get_command_help(self) -> str:
        """Return formatted help text for all available commands."""
        help_text = "🎮 AVAILABLE COMMANDS:\n\n"
        
        categories = {
            "📚 Campaign Management": [
                "list campaigns - Show available campaigns",
                "select campaign [number] - Choose a campaign",
                "campaign info - Show current campaign details",
                "add player to game [player] [campaign] - Add player to campaign",
                "get campaign context [campaign] - Get campaign context"
            ],
            "👥 Character & Player Management": [
                "list players - Show all players",
                "create character [name] - Create new character",
                "update character [name] [field] [value] - Update character",
                "roll ability scores [method] - Roll ability scores",
                "calculate modifier [score] - Calculate ability modifier"
            ],
            "⚔️ Combat System": [
                "start combat - Begin combat encounter",
                "combat status - Show initiative order",
                "next turn - Advance to next combatant",
                "end combat - Finish combat encounter",
                "cast spell [spell] [level] [target] - Cast spell in combat",
                "apply damage [target] [amount] [type] - Apply damage",
                "apply healing [target] [amount] - Apply healing",
                "add condition [target] [condition] - Add status condition",
                "remove condition [target] [condition] - Remove condition"
            ],
            "📈 Experience & Progression": [
                "level up [character] - Level up character",
                "calculate encounter xp [monsters] [party] - Calculate encounter XP",
                "award milestone [character] [description] - Award milestone",
                "get level progression [character] - Show level progress",
                "bulk level party [characters] [levels] - Level up party"
            ],
            "🎒 Inventory & Items": [
                "show inventory [character] - Display character items",
                "search items [query] - Search for items",
                "get item info [item] - Get item details",
                "transfer item [from] [to] [item] - Transfer items",
                "get armor class [character] - Calculate AC",
                "calculate carrying capacity [strength] - Check carry capacity"
            ],
            "⏰ Session Management": [
                "short rest - Take a short rest",
                "long rest - Take a long rest",
                "advance time [amount] [unit] - Advance game time",
                "get session status - Show session information"
            ],
            "🎭 NPC Management": [
                "talk to npc [name] [message] - Generate NPC dialogue",
                "npc behavior [context] - Generate NPC behavior",
                "npc status [name] - Show NPC status",
                "get npc relationships [name] - Show NPC relationships"
            ],
            "⚖️ Rule Enforcement": [
                "rule [topic] - Look up D&D rules",
                "validate action [action] - Validate game action",
                "validate spell cast [spell] - Validate spell casting",
                "get rule summary [topic] - Get rule summary"
            ],
            "🎲 Dice & Random": [
                "roll [dice] - Roll dice (e.g., 'roll 1d20', 'roll 3d6+2')",
                "roll hit points [die] [level] [con] - Roll HP for level",
                "get roll history - Show recent rolls"
            ],
            "🎬 Scenarios & Stories": [
                "generate scenario - Create new story scenario",
                "select option [number] - Choose story option",
                "generate scenario advanced - Advanced scenario creation"
            ],
            "📚 Knowledge System": [
                "retrieve documents [query] - Search knowledge base",
                "query rules [rule_query] - Query rule database",
                "get collection info - Show knowledge collection info"
            ],
            "🎮 Game Engine": [
                "save game [name] - Save current game state",
                "load game [name] - Load saved game",
                "list saves - Show available save files",
                "get game state - Show current game state",
                "agent status - Show system status"
            ]
        }
        
        for category, commands in categories.items():
            help_text += f"{category}:\n"
            for command in commands:
                help_text += f"  • {command}\n"
            help_text += "\n"
        
        help_text += "💬 You can also ask any general D&D question for RAG-powered answers!\n"
        help_text += "📋 Total Commands Available: 126+ commands across all categories"
        return help_text
    
    def _is_numeric_selection(self, instruction_lower: str) -> bool:
        """Check if instruction is a numeric selection."""
        # Handle campaign selection
        if instruction_lower.isdigit() and self.last_command == "list_campaigns":
            return True
        
        # Handle scenario option selection (support "1", "1.", etc.)
        clean_input = instruction_lower.rstrip('.')
        if clean_input.isdigit() and self.last_scenario_options:
            return True
            
        return False
    
    def _handle_numeric_selection(self, instruction_lower: str) -> str:
        """Handle numeric campaign or scenario option selection."""
        clean_input = instruction_lower.rstrip('.')
        
        # Campaign selection
        if self.last_command == "list_campaigns":
            campaign_idx = int(clean_input) - 1
            response = self._send_message_and_wait_safe("campaign_manager", "select_campaign", {"index": campaign_idx})
            self.last_command = ""
            if response and response.get("success"):
                return f"✅ Selected campaign: {response['campaign']}"
            else:
                return f"❌ {response.get('error', 'Failed to select campaign')}"
        
        # Scenario option selection
        elif self.last_scenario_options:
            option_number = int(clean_input)
            return self._select_player_option(option_number)
        
        return f"❌ Invalid numeric selection"
    
    def _parse_command(self, instruction: str) -> tuple:
        """Parse command into agent_id, action, and parameters."""
        instruction_lower = instruction.lower().strip()
        
        # PRIORITY 1: Handle parameterized patterns FIRST (before command_map matching)
        if instruction_lower.startswith('select option'):
            match = re.search(r'select option (\d+)', instruction_lower)
            if match:
                return 'scenario_generator', 'apply_player_choice', {'option_number': int(match.group(1))}
        elif instruction_lower.startswith('roll '):
            return 'dice_system', 'roll_dice', {}
        elif instruction_lower.startswith('rule ') or 'how does' in instruction_lower or self._is_condition_query(instruction_lower):
            return 'rule_enforcement', 'check_rule', {}
        elif self._is_scenario_request(instruction_lower):
            return 'scenario_generator', 'generate_scenario', {}
        
        # PRIORITY 2: Then check command map for exact matches
        # Sort patterns by length in descending order to prefer specific matches
        sorted_patterns = sorted(self.command_map.items(), key=lambda x: len(x[0]), reverse=True)
        for pattern, (agent, action) in sorted_patterns:
            if pattern in instruction_lower:
                params = self._extract_params(instruction)
                return agent, action, params
        
        # No specific command found
        return None, None, {}
    
    def _route_command(self, agent_id: str, action: str, instruction: str, params: dict) -> str:
        """Route command to appropriate agent handler."""
        try:
            # Check if agent is available
            if not self._check_agent_availability(agent_id, action):
                return f"❌ Agent {agent_id} not available or missing handler for {action}"
            
            # Route to appropriate handler based on agent and action
            if agent_id == 'campaign_manager':
                return self._handle_campaign_command(action, params)
            elif agent_id == 'combat_engine':
                return self._handle_combat_command(action, params)
            elif agent_id == 'dice_system':
                return self._handle_dice_roll(instruction)
            elif agent_id == 'rule_enforcement':
                return self._handle_rule_enforcement_command(action, params, instruction)
            elif agent_id == 'game_engine':
                return self._handle_game_engine_command(action, params)
            elif agent_id == 'haystack_pipeline':
                return self._handle_haystack_command(action, params, instruction)
            elif agent_id == 'scenario_generator':
                return self._handle_scenario_command(action, params, instruction)
            elif agent_id == 'session_manager':
                return self._handle_session_command(action, params)
            elif agent_id == 'inventory_manager':
                return self._handle_inventory_command(action, params)
            elif agent_id == 'spell_manager':
                return self._handle_spell_command(action, params)
            elif agent_id == 'character_manager':
                return self._handle_character_command(action, params)
            elif agent_id == 'experience_manager':
                return self._handle_experience_command(action, params)
            elif agent_id == 'npc_controller':
                return self._handle_npc_command(action, params, instruction)
            elif agent_id == 'orchestrator':
                return self._get_system_status()
            else:
                return self._handle_general_query(instruction)
                
        except Exception as e:
            if self.dm_assistant.verbose:
                print(f"❌ Error routing command: {e}")
            return f"❌ Error processing command: {str(e)}"
    
    # Command handler methods
    def _handle_campaign_command(self, action: str, params: dict) -> str:
        """Handle campaign-related commands."""
        if action == 'list_campaigns':
            response = self._send_message_and_wait_safe("campaign_manager", "list_campaigns", {})
            if response:
                campaigns = response.get("campaigns", [])
                if campaigns:
                    self.last_command = "list_campaigns"
                    return "📚 AVAILABLE CAMPAIGNS:\n" + "\n".join(campaigns) + "\n\n💡 *Type the campaign number to select it*"
                else:
                    return "❌ No campaigns available. Check campaigns directory."
            return "❌ Failed to retrieve campaigns"
        
        elif action == 'get_campaign_info':
            response = self._send_message_and_wait_safe("campaign_manager", "get_campaign_info", {})
            if response and response.get("success"):
                return self._format_campaign_info(response["campaign"])
            else:
                return f"❌ {response.get('error', 'No campaign selected')}"
        
        elif action == 'list_players':
            response = self._send_message_and_wait_safe("campaign_manager", "list_players", {})
            if response:
                return self._format_player_list(response.get("players", []))
            return "❌ Failed to retrieve players"
        
        # Phase 4: Campaign Management Extensions
        elif action == 'add_player_to_game':
            player_name = params.get('param_1', '')
            campaign_name = params.get('param_2', '')
            
            if not player_name or not campaign_name:
                return "❌ Usage: add player to game [player_name] [campaign_name]"
            
            result = self._send_message_and_wait_safe("campaign_manager", "add_player_to_game", {
                "player_name": player_name,
                "campaign_name": campaign_name
            })
            if result and result.get("success"):
                return f"👤 **PLAYER ADDED TO CAMPAIGN!**\n🎯 **{player_name}** joined **{campaign_name}**\n{result.get('message', '')}"
            else:
                return f"❌ Failed to add {player_name} to {campaign_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_campaign_context':
            campaign_name = params.get('param_1', '')
            
            if not campaign_name:
                return "❌ Usage: get campaign context [campaign_name]"
            
            result = self._send_message_and_wait_safe("campaign_manager", "get_campaign_context", {
                "campaign_name": campaign_name
            })
            if result and result.get("success"):
                context = result.get('campaign_context', {})
                context_text = f"📖 **CAMPAIGN CONTEXT: {campaign_name}**\n"
                context_text += f"🎭 **Theme**: {context.get('theme', 'Unknown')}\n"
                context_text += f"🗺️ **Setting**: {context.get('setting', 'Unknown')}\n"
                context_text += f"📊 **Session Count**: {context.get('session_count', 0)}\n"
                context_text += f"👥 **Active Players**: {len(context.get('players', []))}\n"
                context_text += f"📍 **Current Location**: {context.get('current_location', 'Unknown')}\n"
                return context_text
            else:
                return f"❌ Failed to get campaign context for {campaign_name}: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown campaign action: {action}"
    
    def _handle_combat_command(self, action: str, params: dict) -> str:
        """Handle combat-related commands."""
        if action == 'start_combat':
            # Add players to combat
            players_response = self._send_message_and_wait_safe("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                for player in players_response["players"]:
                    self._send_message_and_wait_safe("combat_engine", "add_combatant", {
                        "name": player["name"],
                        "max_hp": player.get("hp", 20),
                        "armor_class": player.get("combat_stats", {}).get("armor_class", 12),
                        "is_player": True
                    })
            
            # Start combat
            response = self._send_message_and_wait_safe("combat_engine", "start_combat", {})
            if response and response.get("success"):
                return "⚔️ **COMBAT STARTED!**\n\nUse 'combat status' to see initiative order and 'next turn' to advance."
            else:
                return f"❌ Failed to start combat: {response.get('error', 'Unknown error')}"
        
        elif action == 'get_combat_status':
            response = self._send_message_and_wait_safe("combat_engine", "get_combat_status", {})
            if response and response.get("success"):
                return self._format_combat_status(response["status"])
            else:
                return f"❌ Failed to get combat status: {response.get('error', 'Unknown error')}"
        
        elif action == 'next_turn':
            response = self._send_message_and_wait_safe("combat_engine", "next_turn", {})
            if response and response.get("success"):
                current = response.get("current_combatant")
                if current:
                    return f"🔄 **Turn advanced!**\n🎯 **Now active:** {current['name']}"
                return "🔄 Turn advanced"
            else:
                return f"❌ Failed to advance turn: {response.get('error', 'Unknown error')}"
        
        elif action == 'end_combat':
            response = self._send_message_and_wait_safe("combat_engine", "end_combat", {})
            if response and response.get("success"):
                return "🏁 **COMBAT ENDED!**"
            else:
                return f"❌ Failed to end combat: {response.get('error', 'Unknown error')}"
        
        # Phase 2: Combat System Enhancements
        elif action == 'cast_spell':
            spell_name = params.get('param_1', 'magic missile')
            level = int(params.get('param_2', '1')) if params.get('param_2', '').isdigit() else 1
            target = params.get('param_3', None)
            
            result = self._send_message_and_wait_safe("combat_engine", "cast_spell", {
                "caster_id": "current_player",
                "spell_name": spell_name,
                "spell_level": level,
                "targets": [target] if target else []
            })
            if result and result.get("success"):
                return f"✨ **SPELL CAST!**\n🎯 **{spell_name}** (Level {level})\n{result.get('message', 'Spell cast successfully')}"
            else:
                return f"❌ Failed to cast {spell_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'apply_damage':
            target = params.get('param_1', 'target')
            try:
                amount = int(params.get('param_2', '1'))
            except (ValueError, TypeError):
                return "❌ Damage amount must be a number"
            damage_type = params.get('param_3', 'untyped')
            
            result = self._send_message_and_wait_safe("combat_engine", "apply_damage", {
                "target_id": target,
                "damage": amount,
                "damage_type": damage_type
            })
            if result and result.get("success"):
                return f"⚔️ **DAMAGE APPLIED!**\n🎯 **{target}** takes {amount} {damage_type} damage\n{result.get('message', '')}"
            else:
                return f"❌ Failed to apply damage to {target}: {result.get('error', 'Unknown error')}"
        
        elif action == 'apply_healing':
            target = params.get('param_1', 'target')
            try:
                amount = int(params.get('param_2', '1'))
            except (ValueError, TypeError):
                return "❌ Healing amount must be a number"
            
            result = self._send_message_and_wait_safe("combat_engine", "apply_healing", {
                "target_id": target,
                "healing": amount
            })
            if result and result.get("success"):
                return f"💚 **HEALING APPLIED!**\n🎯 **{target}** recovers {amount} HP\n{result.get('message', '')}"
            else:
                return f"❌ Failed to heal {target}: {result.get('error', 'Unknown error')}"
        
        elif action == 'add_condition':
            target = params.get('param_1', 'target')
            condition = params.get('param_2', 'poisoned')
            duration = params.get('param_3', None)
            
            result = self._send_message_and_wait_safe("combat_engine", "add_condition", {
                "target_id": target,
                "condition": condition,
                "duration": duration
            })
            if result and result.get("success"):
                duration_text = f" for {duration}" if duration else ""
                return f"🌟 **CONDITION ADDED!**\n🎯 **{target}** is now **{condition}**{duration_text}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to add {condition} to {target}: {result.get('error', 'Unknown error')}"
        
        elif action == 'remove_condition':
            target = params.get('param_1', 'target')
            condition = params.get('param_2', 'poisoned')
            
            result = self._send_message_and_wait_safe("combat_engine", "remove_condition", {
                "target_id": target,
                "condition": condition
            })
            if result and result.get("success"):
                return f"✨ **CONDITION REMOVED!**\n🎯 **{target}** is no longer **{condition}**\n{result.get('message', '')}"
            else:
                return f"❌ Failed to remove {condition} from {target}: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown combat action: {action}"
    
    def _handle_dice_roll(self, instruction: str) -> str:
        """Handle dice rolling commands."""
        # Extract action if it's a structured command
        words = instruction.lower().split()
        if len(words) >= 3 and words[1] == 'hit' and words[2] == 'points':
            return self._handle_dice_hit_points(instruction)
        elif 'history' in instruction.lower():
            if 'clear' in instruction.lower():
                return self._handle_clear_roll_history()
            else:
                return self._handle_get_roll_history(instruction)
        
        # Default dice rolling
        response = self._send_message_and_wait_safe("dice_system", "roll_dice", {
            "expression": "1d20",  # Default, could be enhanced
            "context": "Manual roll",
            "skill": None
        })
        
        if response and response.get("success"):
            result = response["result"]
            return f"🎲 **DICE ROLL**\n**Result:** {result['description']}"
        else:
            return f"❌ Failed to roll dice: {response.get('error', 'Unknown error')}"
    
    def _handle_dice_hit_points(self, instruction: str) -> str:
        """Handle hit points rolling command."""
        words = instruction.split()
        hit_die = words[3] if len(words) > 3 else 'd8'
        level = int(words[4]) if len(words) > 4 and words[4].isdigit() else 1
        con_mod = int(words[5]) if len(words) > 5 and words[5].lstrip('-').isdigit() else 0
        
        result = self._send_message_and_wait_safe("dice_system", "roll_hit_points", {
            "hit_die": hit_die,
            "level": level,
            "constitution_modifier": con_mod
        })
        if result and result.get("success"):
            hp_info = result.get('hit_points_info', {})
            return f"❤️ **HIT POINTS ROLLED!**\n🎲 **Hit Die**: {hit_die}\n📊 **Level**: {level}\n💪 **Con Modifier**: {con_mod:+d}\n❤️ **Total HP**: {hp_info.get('total_hp', 0)}\n🎯 **Roll Details**: {hp_info.get('roll_details', 'No details')}"
        else:
            return f"❌ Failed to roll hit points: {result.get('error', 'Unknown error')}"
    
    def _handle_get_roll_history(self, instruction: str) -> str:
        """Handle get roll history command."""
        words = instruction.split()
        limit = 10  # default limit
        for i, word in enumerate(words):
            if word.isdigit():
                limit = int(word)
                break
        
        result = self._send_message_and_wait_safe("dice_system", "get_roll_history", {
            "limit": limit
        })
        if result and result.get("success"):
            history = result.get('roll_history', [])
            if history:
                history_text = "\n".join([f"🎲 **{i+1}.** {roll.get('description', 'Unknown roll')} - {roll.get('timestamp', 'Unknown time')}" for i, roll in enumerate(history[:limit])])
                return f"📜 **ROLL HISTORY** (Last {len(history)} rolls)\n\n{history_text}"
            else:
                return "📜 **ROLL HISTORY** is empty"
        else:
            return f"❌ Failed to get roll history: {result.get('error', 'Unknown error')}"
    
    def _handle_clear_roll_history(self) -> str:
        """Handle clear roll history command."""
        result = self._send_message_and_wait_safe("dice_system", "clear_roll_history", {})
        if result and result.get("success"):
            return f"🗑️ **ROLL HISTORY CLEARED!**\n{result.get('message', 'Roll history has been cleared')}"
        else:
            return f"❌ Failed to clear roll history: {result.get('error', 'Unknown error')}"
    
    def _handle_rule_query(self, instruction: str) -> str:
        """Handle rule checking commands."""
        response = self._send_message_and_wait_safe("rule_enforcement", "check_rule", {
            "query": instruction,
            "category": "general"
        })
        
        if response and response.get("success"):
            rule_info = response["rule_info"]
            return f"📖 **RULE INFO**\n{rule_info['rule_text']}"
        else:
            return f"❌ Failed to find rule: {response.get('error', 'Unknown error')}"
    
    def _handle_game_engine_command(self, action: str, params: dict) -> str:
        """Handle game engine commands."""
        if action == 'list_saves':
            saves = self.dm_assistant.game_save_manager.list_game_saves()
            if not saves:
                return "❌ No game saves found"
            
            output = "💾 AVAILABLE GAME SAVES:\n\n"
            for i, save in enumerate(saves, 1):
                output += f"  {i}. **{save['save_name']}** - {save['campaign']} ({save['last_modified']})\n"
            
            output += "\n💡 *Type 'load save [number]' to load a specific save*"
            return output
        
        # Phase 4: Game Engine Administrative Commands
        elif action == 'enqueue_action':
            action_data = params.get('param_1', '')
            
            if not action_data:
                return "❌ Usage: enqueue action [action_description]"
            
            result = self._send_message_and_wait_safe("game_engine", "enqueue_action", {
                "action_data": action_data,
                "priority": "normal"
            })
            if result and result.get("success"):
                return f"📥 **ACTION QUEUED!**\n📋 **Action**: {action_data}\n🔢 **Queue Position**: {result.get('queue_position', '?')}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to enqueue action: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_game_state':
            result = self._send_message_and_wait_safe("game_engine", "get_game_state", {})
            if result and result.get("success"):
                game_state = result.get('game_state', {})
                state_text = f"🎮 **GAME STATE**\n"
                state_text += f"📊 **Phase**: {game_state.get('current_phase', 'Unknown')}\n"
                state_text += f"🎯 **Active Players**: {len(game_state.get('active_players', []))}\n"
                state_text += f"⏱️ **Turn Count**: {game_state.get('turn_count', 0)}\n"
                state_text += f"📍 **Location**: {game_state.get('current_location', 'Unknown')}\n"
                return state_text
            else:
                return f"❌ Failed to get game state: {result.get('error', 'Unknown error')}"
        
        elif action == 'update_game_state':
            updates = params.get('param_1', '')
            
            if not updates:
                return "❌ Usage: update game state [update_description]"
            
            result = self._send_message_and_wait_safe("game_engine", "update_game_state", {
                "updates": updates,
                "source": "manual_command"
            })
            if result and result.get("success"):
                return f"🔄 **GAME STATE UPDATED!**\n📝 **Changes**: {updates}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to update game state: {result.get('error', 'Unknown error')}"
        
        elif action == 'process_player_action':
            player_action = params.get('param_1', '')
            
            if not player_action:
                return "❌ Usage: process player action [action_description]"
            
            result = self._send_message_and_wait_safe("game_engine", "process_player_action", {
                "player_action": player_action,
                "context": "manual_processing"
            })
            if result and result.get("success"):
                return f"⚙️ **PLAYER ACTION PROCESSED!**\n🎭 **Action**: {player_action}\n📊 **Result**: {result.get('action_result', 'Processed')}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to process player action: {result.get('error', 'Unknown error')}"
        
        elif action == 'should_generate_scene':
            result = self._send_message_and_wait_safe("game_engine", "should_generate_scene", {})
            if result and result.get("success"):
                should_generate = result.get('should_generate', False)
                recommendation = "✅ **YES**" if should_generate else "❌ **NO**"
                return f"🎬 **SCENE GENERATION CHECK**\n{recommendation} - Generate new scene\n📋 **Reason**: {result.get('reason', 'No reason provided')}"
            else:
                return f"❌ Failed to check scene generation: {result.get('error', 'Unknown error')}"
        
        elif action == 'add_scene_to_history':
            scene_data = params.get('param_1', '')
            
            if not scene_data:
                return "❌ Usage: add scene to history [scene_description]"
            
            result = self._send_message_and_wait_safe("game_engine", "add_scene_to_history", {
                "scene_data": scene_data,
                "timestamp": "now"
            })
            if result and result.get("success"):
                return f"📚 **SCENE ADDED TO HISTORY!**\n🎬 **Scene**: {scene_data}\n📊 **History Size**: {result.get('history_size', '?')} scenes\n{result.get('message', '')}"
            else:
                return f"❌ Failed to add scene to history: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown game engine action: {action}"
    
    def _handle_haystack_command(self, action: str, params: dict, instruction: str) -> str:
        """Handle haystack pipeline and knowledge system commands."""
        if action == 'query_rag':
            # Legacy RAG query support
            return self._handle_rag_query(instruction)
        
        # Phase 3: Knowledge & Information System Extensions
        elif action == 'retrieve_documents':
            query = params.get('param_1', instruction)
            try:
                max_docs = int(params.get('param_2', '5'))
            except (ValueError, TypeError):
                max_docs = 5
            
            result = self._send_message_and_wait_safe("haystack_pipeline", "retrieve_documents", {
                "query": query,
                "max_documents": max_docs
            })
            if result and result.get("success"):
                documents = result.get('documents', [])
                docs_text = "\n".join([f"📄 **{i+1}.** {doc.get('title', 'Document')} - {doc.get('content', 'No content')[:100]}..." for i, doc in enumerate(documents[:max_docs])])
                return f"📚 **RETRIEVED DOCUMENTS**\n🔍 Query: {query}\n\n{docs_text}" if docs_text else f"📚 **NO DOCUMENTS FOUND** for query: {query}"
            else:
                return f"❌ Failed to retrieve documents: {result.get('error', 'Unknown error')}"
        
        elif action == 'query_rules':
            rule_query = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("haystack_pipeline", "query_rules", {
                "rule_query": rule_query,
                "include_context": True
            })
            if result and result.get("success"):
                rule_result = result.get('rule_result', {})
                return f"📖 **RULE QUERY RESULT**\n🔍 Query: {rule_query}\n\n📋 **Answer**: {rule_result.get('answer', 'No answer found')}\n📚 **Sources**: {', '.join(rule_result.get('sources', ['No sources']))}"
            else:
                return f"❌ Failed to query rules: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_pipeline_status':
            result = self._send_message_and_wait_safe("haystack_pipeline", "get_pipeline_status", {})
            if result and result.get("success"):
                pipeline_status = result.get('pipeline_status', {})
                return f"🔧 **PIPELINE STATUS**\n🟢 **Status**: {pipeline_status.get('status', 'Unknown')}\n📊 **Documents Indexed**: {pipeline_status.get('documents_count', 0)}\n💾 **Memory Usage**: {pipeline_status.get('memory_usage', 'Unknown')}\n⏱️ **Last Update**: {pipeline_status.get('last_update', 'Unknown')}"
            else:
                return f"❌ Failed to get pipeline status: {result.get('error', 'Unknown error')}"
        
        # Phase 4: Advanced Rule & Knowledge Extensions
        elif action == 'get_collection_info':
            result = self._send_message_and_wait_safe("haystack_pipeline", "get_collection_info", {})
            if result and result.get("success"):
                collection_info = result.get('collection_info', {})
                return f"📚 **COLLECTION INFORMATION**\n📊 **Total Documents**: {collection_info.get('document_count', 0)}\n💾 **Storage Size**: {collection_info.get('storage_size', 'Unknown')}\n📈 **Index Status**: {collection_info.get('index_status', 'Unknown')}\n🔄 **Last Updated**: {collection_info.get('last_updated', 'Unknown')}\n🏷️ **Collections**: {', '.join(collection_info.get('collections', ['None']))}"
            else:
                return f"❌ Failed to get collection info: {result.get('error', 'Unknown error')}"
        
        else:
            # Fallback to general RAG query for unknown actions
            return self._handle_rag_query(instruction)
    
    def _handle_rag_query(self, instruction: str) -> str:
        """Handle direct RAG queries (not scenario generation)."""
        response = self._send_message_and_wait_safe("haystack_pipeline", "query_rag", {
            "query": instruction
        }, timeout=10.0)  # Increased timeout for RAG queries
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            return f"💡 {answer}"
        else:
            return f"❌ Failed to process query: {response.get('error', 'Unknown error')}"
    
    def _handle_scenario_command(self, action: str, params: dict, instruction: str = "") -> str:
        """Handle scenario-related commands with updated RAG-first flow."""
        if action == 'apply_player_choice':
            option_number = params.get('option_number', 1)
            return self._select_player_option(option_number)
        elif action == 'generate_scenario':
            return self._handle_scenario_generation(instruction)
        
        # Phase 4: Advanced Scenario Generation Commands - Updated for RAG-first architecture
        elif action == 'generate_scenario':
            # Extract context from parameters if provided
            context = params.get('param_1', instruction) or instruction
            
            result = self._send_message_and_wait_safe("scenario_generator", "generate_scenario", {
                "query": context,
                "campaign_context": self._get_current_campaign_context(),
                "game_state": self._get_current_game_state_for_scenarios(),
                "use_rag": True
            })
            if result and result.get("success"):
                scenario = result.get('scenario', {})
                rag_info = ""
                if result.get('used_rag'):
                    rag_info = f"\n🔍 **RAG Enhanced**: {result.get('source_count', 0)} D&D sources used"
                
                return f"🎭 **SCENARIO GENERATED!**{rag_info}\n📖 **Scene**: {scenario.get('scenario_text', 'No description')}\n📝 **Options**: {len(scenario.get('options', []))} player choices available"
            else:
                return f"❌ Failed to generate scenario: {result.get('error', 'Unknown error')}"
        
        elif action == 'apply_player_choice':
            state = params.get('param_1', self._get_current_game_state_for_scenarios())
            player = params.get('param_2', 'DM')
            choice = params.get('param_3', '1')
            
            result = self._send_message_and_wait_safe("scenario_generator", "apply_player_choice", {
                "game_state": state,
                "player": player,
                "choice": int(choice) if choice.isdigit() else 1
            })
            if result and result.get("success"):
                return f"✅ **PLAYER CHOICE APPLIED!**\n👤 **Player**: {player}\n🎯 **Choice**: {choice}\n📖 **Consequence**: {result.get('continuation', 'Choice processed')}"
            else:
                return f"❌ Failed to apply player choice: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_generator_status':
            result = self._send_message_and_wait_safe("scenario_generator", "get_generator_status", {})
            if result and result.get("success"):
                # Updated to show new RAG metrics from refactored generator
                llm_available = result.get('llm_available', False)
                rag_metrics = result.get('rag_metrics', {})
                
                status_text = f"🎬 **SCENARIO GENERATOR STATUS**\n"
                status_text += f"🤖 **LLM Available**: {'✅ Yes' if llm_available else '❌ No'}\n"
                status_text += f"🔍 **RAG Requests**: {rag_metrics.get('requests_made', 0)}\n"
                status_text += f"✅ **RAG Success Rate**: {rag_metrics.get('success_rate', 0):.1f}%\n"
                status_text += f"📊 **Architecture**: RAG-First with Orchestrator Communication"
                
                return status_text
            else:
                return f"❌ Failed to get generator status: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown scenario action: {action}"
    
    def _handle_scenario_generation(self, instruction: str) -> str:
        """Handle scenario generation using refactored RAG-first scenario generator."""
        response = self._send_message_and_wait_safe("scenario_generator", "generate_scenario", {
            "query": instruction,
            "campaign_context": self._get_current_campaign_context(),
            "game_state": self._get_current_game_state_for_scenarios(),
            "use_rag": True
        }, timeout=MAX_TIMEOUT)  # Increased timeout for LLM-based scenario generation
        
        if response and response.get("success"):
            scenario = response.get("scenario", {})
            scenario_text = scenario.get("scenario_text", "Failed to generate scenario")
            options = scenario.get("options", [])
            
            # Build response with RAG enhancement info
            rag_info = ""
            if response.get('used_rag'):
                source_count = response.get('source_count', 0)
                rag_info = f"\n🔍 **Enhanced with {source_count} D&D knowledge sources**"
            
            # Store options for later selection
            if options:
                self.last_scenario_options = options
                options_text = "\n".join(options)
                return f"🎭 **SCENARIO:**{rag_info}\n{scenario_text}\n\n**OPTIONS:**\n{options_text}\n\n📝 *Type 'select option [number]' to choose a player option.*"
            else:
                return f"🎭 **SCENARIO:**{rag_info}\n{scenario_text}"
        else:
            return f"❌ Failed to generate scenario: {response.get('error', 'Unknown error')}"
    
    def _handle_session_command(self, action: str, params: dict) -> str:
        """Handle session-related commands."""
        if action == 'take_short_rest':
            response = self._send_message_and_wait_safe("session_manager", "take_short_rest", {})
            if response and response.get("success"):
                return f"😴 **SHORT REST COMPLETED!**\n{response['message']}"
            else:
                return f"❌ Failed to take short rest: {response.get('error', 'Unknown error')}"
        
        elif action == 'take_long_rest':
            response = self._send_message_and_wait_safe("session_manager", "take_long_rest", {})
            if response and response.get("success"):
                return f"🛌 **LONG REST COMPLETED!**\n{response['message']}"
            else:
                return f"❌ Failed to take long rest: {response.get('error', 'Unknown error')}"
        
        # Phase 2: Session Management Extensions
        elif action == 'advance_time':
            time_amount = params.get('param_1', '1')
            time_unit = params.get('param_2', 'hours')
            
            result = self._send_message_and_wait_safe("session_manager", "advance_time", {
                "amount": time_amount,
                "unit": time_unit
            })
            if result and result.get("success"):
                return f"⏰ **TIME ADVANCED!**\n🕐 **{time_amount} {time_unit}** passed\n{result.get('message', '')}"
            else:
                return f"❌ Failed to advance time: {result.get('error', 'Unknown error')}"
        
        elif action == 'check_rest_eligibility':
            players = params.get('param_1', '').split(',') if params.get('param_1') else []
            
            result = self._send_message_and_wait_safe("session_manager", "check_rest_eligibility", {
                "players": players
            })
            if result and result.get("success"):
                eligibility = result.get('rest_eligibility', {})
                eligibility_text = "\n".join([f"• **{player}**: {status}" for player, status in eligibility.items()])
                return f"😴 **REST ELIGIBILITY CHECK**\n\n{eligibility_text}"
            else:
                return f"❌ Failed to check rest eligibility: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_session_info':
            result = self._send_message_and_wait_safe("session_manager", "get_session_info", {})
            if result and result.get("success"):
                session_info = result.get('session_info', {})
                info_text = f"📊 **SESSION INFORMATION**\n"
                info_text += f"🕐 **Current Time**: {session_info.get('current_time', 'Unknown')}\n"
                info_text += f"📅 **Session Duration**: {session_info.get('duration', 'Unknown')}\n"
                info_text += f"🎯 **Active Events**: {len(session_info.get('active_events', []))}\n"
                if session_info.get('last_rest'):
                    info_text += f"😴 **Last Rest**: {session_info['last_rest']}\n"
                return info_text
            else:
                return f"❌ Failed to get session info: {result.get('error', 'Unknown error')}"
        
        # Phase 3: Advanced Session Management Extensions
        elif action == 'get_rest_status':
            character_name = params.get('param_1', '') or None
            
            result = self._send_message_and_wait_safe("session_manager", "get_rest_status", {
                "character_name": character_name
            })
            if result and result.get("success"):
                rest_status = result.get('rest_status', {})
                if character_name:
                    return f"😴 **REST STATUS: {character_name}**\n⏰ **Last Short Rest**: {rest_status.get('last_short_rest', 'Never')}\n🛌 **Last Long Rest**: {rest_status.get('last_long_rest', 'Never')}\n✅ **Can Short Rest**: {rest_status.get('can_short_rest', True)}\n✅ **Can Long Rest**: {rest_status.get('can_long_rest', True)}"
                else:
                    status_text = "😴 **PARTY REST STATUS**\n"
                    for char, status in rest_status.items():
                        status_text += f"• **{char}**: Short Rest ✅ {status.get('can_short_rest', True)}, Long Rest ✅ {status.get('can_long_rest', True)}\n"
                    return status_text
            else:
                return f"❌ Failed to get rest status: {result.get('error', 'Unknown error')}"
        
        elif action == 'add_time':
            try:
                hours = int(params.get('param_1', '0'))
                minutes = int(params.get('param_2', '0'))
            except (ValueError, TypeError):
                return "❌ Time values must be numbers"
            activity = params.get('param_3', 'general activity')
            
            result = self._send_message_and_wait_safe("session_manager", "add_time", {
                "hours": hours,
                "minutes": minutes,
                "activity": activity
            })
            if result and result.get("success"):
                return f"⏰ **TIME ADDED!**\n🕐 **Duration**: {hours}h {minutes}m\n📋 **Activity**: {activity}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to add time: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_session_status':
            result = self._send_message_and_wait_safe("session_manager", "get_session_status", {})
            if result and result.get("success"):
                session_status = result.get('session_status', {})
                status_text = f"📊 **SESSION STATUS**\n"
                status_text += f"🕐 **Current Time**: {session_status.get('current_time', 'Unknown')}\n"
                status_text += f"📅 **Session Duration**: {session_status.get('session_duration', 'Unknown')}\n"
                status_text += f"🎯 **Active Events**: {len(session_status.get('active_events', []))}\n"
                status_text += f"👥 **Party Status**: {session_status.get('party_status', 'Active')}\n"
                if session_status.get('weather'):
                    status_text += f"🌤️ **Weather**: {session_status['weather']}\n"
                return status_text
            else:
                return f"❌ Failed to get session status: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown session action: {action}"
    
    def _handle_inventory_command(self, action: str, params: dict) -> str:
        """Handle inventory-related commands."""
        if action == 'get_inventory':
            response = self._send_message_and_wait_safe("inventory_manager", "get_inventory", {
                "character": params.get('param_1', 'party')
            })
            if response and response.get("success"):
                return self._format_inventory(response.get("inventory", {}))
            else:
                return f"❌ Failed to get inventory: {response.get('error', 'Unknown error')}"
        
        # Phase 2: Inventory Management Extensions
        elif action == 'search_items':
            query = params.get('param_1', '')
            item_type = params.get('param_2', None)
            
            if not query:
                return "❌ Usage: search items [search_query] [optional: item_type]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "search_items", {
                "query": query,
                "item_type": item_type
            })
            if result and result.get("success"):
                items = result.get('items', [])
                if items:
                    items_text = "\n".join([f"• **{item['name']}** - {item.get('description', 'No description')}" for item in items])
                    return f"🔍 **ITEM SEARCH RESULTS**\n📝 Query: {query}\n\n{items_text}"
                else:
                    return f"🔍 **NO ITEMS FOUND** matching '{query}'"
            else:
                return f"❌ Failed to search items: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_item_info':
            item_name = params.get('param_1', '')
            
            if not item_name:
                return "❌ Usage: get item info [item_name]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "get_item_info", {
                "item_name": item_name
            })
            if result and result.get("success"):
                item_info = result.get('item_info', {})
                info_text = f"📋 **{item_info.get('name', item_name)}**\n"
                info_text += f"**Type**: {item_info.get('type', 'Unknown')}\n"
                info_text += f"**Description**: {item_info.get('description', 'No description')}\n"
                if item_info.get('properties'):
                    info_text += f"**Properties**: {', '.join(item_info['properties'])}\n"
                if item_info.get('damage'):
                    info_text += f"**Damage**: {item_info['damage']}\n"
                if item_info.get('ac'):
                    info_text += f"**AC**: {item_info['ac']}\n"
                return info_text
            else:
                return f"❌ Failed to get item info for '{item_name}': {result.get('error', 'Unknown error')}"
        
        elif action == 'transfer_item':
            from_char = params.get('param_1', '')
            to_char = params.get('param_2', '')
            item_name = params.get('param_3', '')
            # param_4 would be quantity, but our simple param extraction doesn't go that far
            
            if not from_char or not to_char or not item_name:
                return "❌ Usage: transfer item [from_character] [to_character] [item_name] [optional: quantity]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "transfer_item", {
                "from_character": from_char,
                "to_character": to_char,
                "item_name": item_name,
                "quantity": 1  # Default quantity
            })
            if result and result.get("success"):
                return f"📦 **ITEM TRANSFERRED!**\n🎯 **{item_name}** moved from {from_char} to {to_char}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to transfer {item_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_armor_class':
            character_name = params.get('param_1', '')
            
            if not character_name:
                return "❌ Usage: get armor class [character_name]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "get_armor_class", {
                "character_name": character_name
            })
            if result and result.get("success"):
                ac_info = result.get('armor_class_info', {})
                return f"🛡️ **ARMOR CLASS CALCULATION**\n🎯 **{character_name}** AC: {ac_info.get('total_ac', '?')}\n📊 **Base AC**: {ac_info.get('base_ac', '10')}\n⚔️ **Armor Bonus**: +{ac_info.get('armor_bonus', '0')}\n🎯 **Dex Modifier**: +{ac_info.get('dex_modifier', '0')}"
            else:
                return f"❌ Failed to calculate AC for {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'initialize_inventory':
            character_name = params.get('param_1', '')
            try:
                strength_score = int(params.get('param_2', '10'))
            except (ValueError, TypeError):
                strength_score = 10
            
            if not character_name:
                return "❌ Usage: initialize inventory [character_name] [optional: strength_score]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "initialize_inventory", {
                "character_name": character_name,
                "strength_score": strength_score
            })
            if result and result.get("success"):
                return f"🎒 **INVENTORY INITIALIZED!**\n🎯 **{character_name}** inventory ready\n💪 **Carrying Capacity**: {result.get('carrying_capacity', '?')} lbs\n{result.get('message', '')}"
            else:
                return f"❌ Failed to initialize inventory for {character_name}: {result.get('error', 'Unknown error')}"
        
        # Phase 3: Advanced Inventory Management Extensions
        elif action == 'calculate_carrying_capacity':
            try:
                strength_score = int(params.get('param_1', '10'))
            except (ValueError, TypeError):
                return "❌ Strength score must be a number"
            
            result = self._send_message_and_wait_safe("inventory_manager", "calculate_carrying_capacity", {
                "strength_score": strength_score
            })
            if result and result.get("success"):
                capacity = result.get('carrying_capacity', {})
                return f"💪 **CARRYING CAPACITY CALCULATION**\n🏋️ **Strength {strength_score}**: {capacity.get('normal_capacity', 0)} lbs\n⚠️ **Heavy Load**: {capacity.get('heavy_load', 0)} lbs\n🛑 **Max Capacity**: {capacity.get('max_capacity', 0)} lbs"
            else:
                return f"❌ Failed to calculate carrying capacity: {result.get('error', 'Unknown error')}"
        
        elif action == 'create_custom_item':
            item_data = params.get('param_1', '')
            
            if not item_data:
                return "❌ Usage: create custom item [item_data_description]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "create_custom_item", {
                "item_description": item_data,
                "auto_generate": True
            })
            if result and result.get("success"):
                item_info = result.get('created_item', {})
                return f"🔨 **CUSTOM ITEM CREATED!**\n📋 **Name**: {item_info.get('name', 'Custom Item')}\n⚖️ **Weight**: {item_info.get('weight', 1)} lbs\n💰 **Value**: {item_info.get('value', 1)} gp\n📝 **Description**: {item_info.get('description', 'Custom created item')}"
            else:
                return f"❌ Failed to create custom item: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_carrying_capacity':
            character_name = params.get('param_1', '')
            
            if not character_name:
                return "❌ Usage: get carrying capacity [character_name]"
            
            result = self._send_message_and_wait_safe("inventory_manager", "get_carrying_capacity", {
                "character_name": character_name
            })
            if result and result.get("success"):
                capacity_info = result.get('capacity_info', {})
                current_weight = capacity_info.get('current_weight', 0)
                max_capacity = capacity_info.get('max_capacity', 150)
                return f"💼 **CARRYING CAPACITY: {character_name}**\n⚖️ **Current Load**: {current_weight} lbs\n🏋️ **Max Capacity**: {max_capacity} lbs\n📊 **Load Percentage**: {capacity_info.get('load_percentage', 0)}%\n🚨 **Status**: {capacity_info.get('encumbrance_status', 'Normal')}"
            else:
                return f"❌ Failed to get carrying capacity for {character_name}: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown inventory action: {action}"
    
    def _handle_spell_command(self, action: str, params: dict) -> str:
        """Handle spell-related commands."""
        if action == 'cast_spell':
            response = self._send_message_and_wait_safe("spell_manager", "cast_spell", {
                "character": params.get('param_2', 'caster'),
                "spell": params.get('param_1', '')
            })
            if response and response.get("success"):
                return f"✨ **SPELL CAST!**\n{response['message']}"
            else:
                return f"❌ Failed to cast spell: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown spell action: {action}"
    
    def _handle_character_command(self, action: str, params: dict) -> str:
        """Handle character-related commands."""
        if action == 'create_character':
            response = self._send_message_and_wait_safe("character_manager", "create_character", {
                "name": params.get('param_1', ''),
                "race": "Human",
                "character_class": "Fighter",
                "level": 1
            })
            if response and response.get("success"):
                return f"🎭 **CHARACTER CREATED!**\n{response['message']}"
            else:
                return f"❌ Failed to create character: {response.get('error', 'Unknown error')}"
        
        # Phase 2: Character Management Extensions
        elif action == 'update_character':
            character_name = params.get('param_1', '')
            field = params.get('param_2', '')
            value = params.get('param_3', '')
            
            if not character_name or not field or not value:
                return "❌ Usage: update character [name] [field] [value]"
            
            result = self._send_message_and_wait_safe("character_manager", "update_character", {
                "character_name": character_name,
                "field": field,
                "value": value
            })
            if result and result.get("success"):
                return f"📝 **CHARACTER UPDATED!**\n🎯 **{character_name}** {field} set to {value}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to update {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'roll_ability_scores':
            method = params.get('param_1', '4d6_drop_lowest')
            
            result = self._send_message_and_wait_safe("character_manager", "roll_ability_scores", {
                "method": method
            })
            if result and result.get("success"):
                scores = result.get('ability_scores', {})
                scores_text = "\n".join([f"**{ability.upper()}**: {score}" for ability, score in scores.items()])
                return f"🎲 **ABILITY SCORES ROLLED!**\n📊 **Method**: {method}\n\n{scores_text}"
            else:
                return f"❌ Failed to roll ability scores: {result.get('error', 'Unknown error')}"
        
        elif action == 'calculate_modifier':
            try:
                ability_score = int(params.get('param_1', '10'))
            except (ValueError, TypeError):
                return "❌ Ability score must be a number"
            
            result = self._send_message_and_wait_safe("character_manager", "calculate_modifier", {
                "ability_score": ability_score
            })
            if result and result.get("success"):
                modifier = result.get('modifier', 0)
                modifier_text = f"+{modifier}" if modifier >= 0 else str(modifier)
                return f"🧮 **ABILITY MODIFIER**\n📊 **Score {ability_score}** → **{modifier_text}**"
            else:
                return f"❌ Failed to calculate modifier: {result.get('error', 'Unknown error')}"
        
        elif action == 'update_ability_scores':
            character_name = params.get('param_1', '')
            # This would need more complex parameter parsing for actual ability score updates
            if not character_name:
                return "❌ Usage: update ability scores [character_name] [scores...]"
            
            result = self._send_message_and_wait_safe("character_manager", "update_ability_scores", {
                "character_name": character_name,
                "ability_scores": {}  # Placeholder - would need complex parsing
            })
            if result and result.get("success"):
                return f"📝 **ABILITY SCORES UPDATED!**\n🎯 **{character_name}** ability scores modified\n{result.get('message', '')}"
            else:
                return f"❌ Failed to update ability scores for {character_name}: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown character action: {action}"
    
    def _handle_experience_command(self, action: str, params: dict) -> str:
        """Handle experience-related commands."""
        if action == 'level_up':
            response = self._send_message_and_wait_safe("experience_manager", "level_up", {
                "character": params.get('param_1', '')
            })
            if response and response.get("success"):
                return f"⬆️ **LEVEL UP!**\n{response['message']}"
            else:
                return f"❌ Failed to level up: {response.get('error', 'Unknown error')}"
        
        # Phase 2: Experience & Progression Extensions
        elif action == 'calculate_encounter_xp':
            monsters = params.get('param_1', '').split(',') if params.get('param_1') else []
            try:
                party_size = int(params.get('param_2', '4'))
            except (ValueError, TypeError):
                party_size = 4
            
            result = self._send_message_and_wait_safe("experience_manager", "calculate_encounter_xp", {
                "monsters": monsters,
                "party_size": party_size
            })
            if result and result.get("success"):
                xp_info = result.get('xp_calculation', {})
                return f"⚔️ **ENCOUNTER XP CALCULATED!**\n🎯 **Total XP**: {xp_info.get('total_xp', 0)}\n👥 **Per Player**: {xp_info.get('xp_per_player', 0)}\n📊 **Difficulty**: {xp_info.get('difficulty', 'Unknown')}"
            else:
                return f"❌ Failed to calculate encounter XP: {result.get('error', 'Unknown error')}"
        
        elif action == 'award_milestone':
            character_name = params.get('param_1', '')
            milestone = params.get('param_2', 'milestone achieved')
            
            if not character_name:
                return "❌ Usage: award milestone [character] [milestone_description]"
            
            result = self._send_message_and_wait_safe("experience_manager", "award_milestone", {
                "character_name": character_name,
                "milestone": milestone
            })
            if result and result.get("success"):
                return f"🏆 **MILESTONE AWARDED!**\n🎯 **{character_name}** achieved: {milestone}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to award milestone to {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'initialize_character_xp':
            character_name = params.get('param_1', '')
            try:
                level = int(params.get('param_2', '1'))
            except (ValueError, TypeError):
                level = 1
            
            if not character_name:
                return "❌ Usage: initialize character xp [character] [starting_level]"
            
            result = self._send_message_and_wait_safe("experience_manager", "initialize_character_xp", {
                "character_name": character_name,
                "starting_level": level
            })
            if result and result.get("success"):
                return f"📊 **XP TRACKING INITIALIZED!**\n🎯 **{character_name}** starting at level {level}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to initialize XP for {character_name}: {result.get('error', 'Unknown error')}"
        
        # Phase 3: Advanced Experience Management Extensions
        elif action == 'get_level_progression':
            character_name = params.get('param_1', '')
            
            if not character_name:
                return "❌ Usage: get level progression [character_name]"
            
            result = self._send_message_and_wait_safe("experience_manager", "get_level_progression", {
                "character_name": character_name
            })
            if result and result.get("success"):
                progression = result.get('level_progression', {})
                current_level = progression.get('current_level', 1)
                current_xp = progression.get('current_xp', 0)
                next_level_xp = progression.get('next_level_xp', 300)
                return f"📈 **LEVEL PROGRESSION: {character_name}**\n🎯 **Current Level**: {current_level}\n✨ **Current XP**: {current_xp}\n🎯 **Next Level XP**: {next_level_xp}\n📊 **Progress**: {progression.get('progress_percentage', 0)}%"
            else:
                return f"❌ Failed to get level progression for {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'set_milestone_progression':
            character_name = params.get('param_1', '')
            
            if not character_name:
                return "❌ Usage: set milestone progression [character_name]"
            
            result = self._send_message_and_wait_safe("experience_manager", "set_milestone_progression", {
                "character_name": character_name,
                "enable_milestone": True
            })
            if result and result.get("success"):
                return f"🏆 **MILESTONE PROGRESSION SET!**\n🎯 **{character_name}** now uses milestone-based leveling\n{result.get('message', '')}"
            else:
                return f"❌ Failed to set milestone progression for {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_xp_to_next_level':
            character_name = params.get('param_1', '')
            
            if not character_name:
                return "❌ Usage: get xp to next level [character_name]"
            
            result = self._send_message_and_wait_safe("experience_manager", "get_xp_to_next_level", {
                "character_name": character_name
            })
            if result and result.get("success"):
                xp_info = result.get('xp_info', {})
                return f"✨ **XP TO NEXT LEVEL: {character_name}**\n🎯 **XP Needed**: {xp_info.get('xp_needed', 0)}\n📊 **Current XP**: {xp_info.get('current_xp', 0)}\n🎯 **Target XP**: {xp_info.get('target_xp', 0)}"
            else:
                return f"❌ Failed to get XP info for {character_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'bulk_level_party':
            characters = params.get('param_1', '').split(',') if params.get('param_1') else []
            try:
                levels = int(params.get('param_2', '1'))
            except (ValueError, TypeError):
                levels = 1
            
            result = self._send_message_and_wait_safe("experience_manager", "bulk_level_party", {
                "characters": characters,
                "levels": levels
            })
            if result and result.get("success"):
                return f"⬆️ **PARTY LEVELED UP!**\n👥 **Characters**: {', '.join(characters)}\n📈 **Levels Gained**: {levels}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to level party: {result.get('error', 'Unknown error')}"
        
        elif action == 'reset_xp':
            character_name = params.get('param_1', '')
            try:
                level = int(params.get('param_2', '1'))
            except (ValueError, TypeError):
                level = 1
            
            if not character_name:
                return "❌ Usage: reset xp [character_name] [optional: target_level]"
            
            result = self._send_message_and_wait_safe("experience_manager", "reset_xp", {
                "character_name": character_name,
                "target_level": level
            })
            if result and result.get("success"):
                return f"🔄 **XP RESET!**\n🎯 **{character_name}** XP reset to level {level}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to reset XP for {character_name}: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown experience action: {action}"
    
    def _handle_npc_command(self, action: str, params: dict, instruction: str) -> str:
        """Handle NPC-related commands."""
        if action == 'generate_npc_dialogue':
            return self._handle_npc_dialogue(instruction, params)
        elif action == 'generate_npc_behavior':
            return self._handle_npc_behavior_generation(instruction, params)
        elif action == 'get_npc_state':
            return self._handle_npc_status(instruction, params)
        elif action == 'update_npc_stats':
            return self._handle_npc_stat_update(instruction, params)
        elif action == 'npc_social_interaction':
            return self._handle_npc_social_interaction(instruction, params)
        
        # Phase 2: NPC Management Extensions
        elif action == 'remove_npc':
            npc_name = params.get('param_1', '').strip()
            
            if not npc_name:
                return "❌ Usage: remove npc [npc_name]"
            
            result = self._send_message_and_wait_safe("npc_controller", "remove_npc", {
                "npc_name": npc_name
            })
            if result and result.get("success"):
                return f"🗑️ **NPC REMOVED!**\n🎯 **{npc_name}** has been removed from the game\n{result.get('message', '')}"
            else:
                return f"❌ Failed to remove {npc_name}: {result.get('error', 'Unknown error')}"
        
        # Phase 4: Advanced NPC Management Extensions
        elif action == 'update_npc':
            npc_name = params.get('param_1', '').strip()
            field = params.get('param_2', '')
            value = params.get('param_3', '')
            
            if not npc_name or not field or not value:
                return "❌ Usage: update npc advanced [npc_name] [field] [value]"
            
            result = self._send_message_and_wait_safe("npc_controller", "update_npc", {
                "npc_name": npc_name,
                "field": field,
                "value": value,
                "advanced_mode": True
            })
            if result and result.get("success"):
                return f"📝 **NPC UPDATED!**\n🎯 **{npc_name}** {field} updated to {value}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to update {npc_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_npc_relationships':
            npc_name = params.get('param_1', '').strip()
            
            if not npc_name:
                return "❌ Usage: get npc relationships [npc_name]"
            
            result = self._send_message_and_wait_safe("npc_controller", "get_npc_relationships", {
                "npc_name": npc_name
            })
            if result and result.get("success"):
                relationships = result.get('relationships', {})
                if relationships:
                    rel_text = "\n".join([f"• **{other_npc}**: {relationship}" for other_npc, relationship in relationships.items()])
                    return f"👥 **NPC RELATIONSHIPS: {npc_name}**\n\n{rel_text}"
                else:
                    return f"👥 **{npc_name}** has no established relationships"
            else:
                return f"❌ Failed to get relationships for {npc_name}: {result.get('error', 'Unknown error')}"
        
        elif action == 'update_npc_relationship':
            npc1 = params.get('param_1', '').strip()
            npc2 = params.get('param_2', '').strip()
            relationship_value = params.get('param_3', '')
            
            if not npc1 or not npc2 or not relationship_value:
                return "❌ Usage: update npc relationship [npc1] [npc2] [relationship_value]"
            
            result = self._send_message_and_wait_safe("npc_controller", "update_npc_relationship", {
                "npc1": npc1,
                "npc2": npc2,
                "relationship_value": relationship_value
            })
            if result and result.get("success"):
                return f"🔗 **RELATIONSHIP UPDATED!**\n👥 **{npc1}** ↔️ **{npc2}**: {relationship_value}\n{result.get('message', '')}"
            else:
                return f"❌ Failed to update relationship: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown NPC action: {action}"
    
    def _handle_rule_enforcement_command(self, action: str, params: dict, instruction: str) -> str:
        """Handle rule enforcement and validation commands."""
        if action == 'validate_action':
            action_data = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("rule_enforcement", "validate_action", {
                "action_data": action_data,
                "context": instruction
            })
            if result and result.get("success"):
                validation = result.get('validation_result', {})
                is_valid = validation.get('is_valid', False)
                status = "✅ **VALID**" if is_valid else "❌ **INVALID**"
                return f"⚖️ **ACTION VALIDATION**\n{status}\n📋 **Details**: {validation.get('details', 'No details provided')}"
            else:
                return f"❌ Failed to validate action: {result.get('error', 'Unknown error')}"
        
        elif action == 'validate_spell_cast':
            spell_data = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("rule_enforcement", "validate_spell_cast", {
                "spell_data": spell_data,
                "context": instruction
            })
            if result and result.get("success"):
                validation = result.get('validation_result', {})
                is_valid = validation.get('is_valid', False)
                status = "✅ **VALID**" if is_valid else "❌ **INVALID**"
                return f"✨ **SPELL VALIDATION**\n{status}\n📋 **Details**: {validation.get('details', 'No details provided')}"
            else:
                return f"❌ Failed to validate spell cast: {result.get('error', 'Unknown error')}"
        
        elif action == 'validate_attack':
            attack_data = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("rule_enforcement", "validate_attack", {
                "attack_data": attack_data,
                "context": instruction
            })
            if result and result.get("success"):
                validation = result.get('validation_result', {})
                is_valid = validation.get('is_valid', False)
                status = "✅ **VALID**" if is_valid else "❌ **INVALID**"
                return f"⚔️ **ATTACK VALIDATION**\n{status}\n📋 **Details**: {validation.get('details', 'No details provided')}"
            else:
                return f"❌ Failed to validate attack: {result.get('error', 'Unknown error')}"
        
        elif action == 'validate_movement':
            movement_data = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("rule_enforcement", "validate_movement", {
                "movement_data": movement_data,
                "context": instruction
            })
            if result and result.get("success"):
                validation = result.get('validation_result', {})
                is_valid = validation.get('is_valid', False)
                status = "✅ **VALID**" if is_valid else "❌ **INVALID**"
                return f"🚶 **MOVEMENT VALIDATION**\n{status}\n📋 **Details**: {validation.get('details', 'No details provided')}"
            else:
                return f"❌ Failed to validate movement: {result.get('error', 'Unknown error')}"
        
        elif action == 'get_rule_summary':
            topic = params.get('param_1', 'general')
            
            result = self._send_message_and_wait_safe("rule_enforcement", "get_rule_summary", {
                "topic": topic
            })
            if result and result.get("success"):
                summary = result.get('rule_summary', {})
                return f"📖 **RULE SUMMARY: {topic.upper()}**\n{summary.get('content', 'No summary available')}\n\n📚 **Source**: {summary.get('source', 'D&D 5e')}"
            else:
                return f"❌ Failed to get rule summary for '{topic}': {result.get('error', 'Unknown error')}"
        
        # Phase 4: Advanced Rule & Knowledge Extensions
        elif action == 'validate_ability_check':
            check_data = params.get('param_1', instruction)
            
            result = self._send_message_and_wait_safe("rule_enforcement", "validate_ability_check", {
                "check_data": check_data,
                "context": instruction
            })
            if result and result.get("success"):
                validation = result.get('validation_result', {})
                is_valid = validation.get('is_valid', False)
                status = "✅ **VALID**" if is_valid else "❌ **INVALID**"
                return f"🎯 **ABILITY CHECK VALIDATION**\n{status}\n📊 **DC**: {validation.get('dc', '?')}\n🎲 **Required Roll**: {validation.get('required_roll', '?')}\n📋 **Details**: {validation.get('details', 'No details provided')}"
            else:
                return f"❌ Failed to validate ability check: {result.get('error', 'Unknown error')}"
        
        return f"❌ Unknown rule enforcement action: {action}"

    def _handle_npc_dialogue(self, instruction: str, params: dict) -> str:
        """Handle NPC dialogue generation requests"""
        npc_name = params.get('param_1', '').strip()
        player_input = params.get('param_2', '').strip()
        
        if not npc_name:
            return "❌ Please specify NPC name. Usage: talk to npc [name] [optional: what to say]"
        
        response = self._send_message_and_wait_safe("npc_controller", "generate_npc_dialogue", {
            "npc_name": npc_name,
            "player_input": player_input,
            "context": "dialogue"
        })
        
        if response and response.get("success"):
            return f"💬 **{npc_name}:** {response['dialogue']}\n\n📊 **Mood:** {response.get('mood', 'neutral')}"
        else:
            return f"❌ Could not generate dialogue for {npc_name}: {response.get('error', 'Unknown error')}"

    def _handle_npc_behavior_generation(self, instruction: str, params: dict) -> str:
        """Handle NPC behavior generation requests"""
        response = self._send_message_and_wait_safe("npc_controller", "generate_npc_behavior", {
            "context": instruction,
            "game_state": self._get_current_game_state()
        })
        
        if response and response.get("success"):
            return f"🎭 **NPC BEHAVIOR:**\n{response['behavior_description']}\n\n📋 **Actions:** {response.get('actions', 'No specific actions')}"
        else:
            return f"❌ Failed to generate NPC behavior: {response.get('error', 'Unknown error')}"

    def _handle_npc_status(self, instruction: str, params: dict) -> str:
        """Handle NPC status requests"""
        npc_name = params.get('param_1', '').strip()
        
        if not npc_name:
            return "❌ Please specify NPC name. Usage: npc status [name]"
        
        response = self._send_message_and_wait_safe("npc_controller", "get_npc_state", {
            "npc_name": npc_name
        })
        
        if response and response.get("success"):
            npc_state = response['npc_state']
            status = f"📊 **{npc_state['name']} STATUS:**\n"
            status += f"**HP:** {npc_state['stats'].get('hp', '?')}/{npc_state['stats'].get('max_hp', '?')}\n"
            status += f"**AC:** {npc_state['stats'].get('ac', '?')}\n"
            status += f"**Location:** {npc_state['location']}\n"
            if npc_state['status_effects']:
                status += f"**Conditions:** {', '.join(npc_state['status_effects'])}\n"
            status += f"**Memory Count:** {npc_state['memory_count']}"
            return status
        else:
            return f"❌ Could not get status for {npc_name}: {response.get('error', 'Unknown error')}"

    def _handle_npc_stat_update(self, instruction: str, params: dict) -> str:
        """Handle NPC stat update requests"""
        npc_name = params.get('param_1', '').strip()
        
        if not npc_name:
            return "❌ Please specify NPC name. Usage: update npc [name]"
        
        # For now, return a placeholder - would need more complex parsing for actual stat updates
        return f"📝 NPC stat update for {npc_name} - Feature requires more detailed implementation"

    def _handle_npc_social_interaction(self, instruction: str, params: dict) -> str:
        """Handle NPC social interaction requests"""
        # Determine interaction type from instruction
        interaction_type = "conversation"
        if "persuade" in instruction.lower():
            interaction_type = "persuasion"
        elif "intimidate" in instruction.lower():
            interaction_type = "intimidation"
        elif "deceive" in instruction.lower():
            interaction_type = "deception"
        
        npc_name = params.get('param_1', '').strip()
        player_action = params.get('param_2', '').strip()
        
        if not npc_name:
            return f"❌ Please specify NPC name. Usage: {interaction_type} [npc_name] [attempt]"
        
        response = self._send_message_and_wait_safe("npc_controller", "npc_social_interaction", {
            "npc_name": npc_name,
            "interaction_type": interaction_type,
            "player_action": player_action,
            "context": {"instruction": instruction}
        })
        
        if response and response.get("success"):
            result = response['interaction_result']
            return f"🎭 **{interaction_type.upper()} ATTEMPT:**\n{result['response']}\n\n📊 **Relationship Change:** {result.get('relationship_change', 0)}"
        else:
            return f"❌ Failed {interaction_type} attempt: {response.get('error', 'Unknown error')}"

    def _get_current_game_state(self) -> dict:
        """Get current game state for NPC context"""
        # This would ideally get the actual game state from the game engine
        # For now, return a basic placeholder
        return {
            "session": {"events": []},
            "players": {},
            "world": {"locations": []}
        }
    
    def _handle_general_query(self, instruction: str) -> str:
        """Handle general queries using RAG."""
        response = self._send_message_and_wait_safe("haystack_pipeline", "query_rag", {"query": instruction}, timeout=10.0)  # Increased timeout for RAG queries
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            return f"💡 {answer}"
        else:
            return f"❌ Failed to process query: {response.get('error', 'Unknown error')}"
    
    def _get_system_status(self) -> str:
        """Get comprehensive system status."""
        status = "🤖 MODULAR DM ASSISTANT STATUS:\n\n"
        
        # Agent status
        agent_status = self.dm_assistant.orchestrator.get_agent_status()
        status += "🎭 AGENT STATUS:\n"
        for agent_id, info in agent_status.items():
            running_status = "🟢 Running" if info["running"] else "🔴 Stopped"
            status += f"  • {agent_id} ({info['agent_type']}): {running_status}\n"
            if info["handlers"]:
                handlers_display = ', '.join(info['handlers'][:3])
                if len(info['handlers']) > 3:
                    handlers_display += f"... (+{len(info['handlers']) - 3} more)"
                status += f"    Handlers: {handlers_display}\n"
        
        # Message bus statistics
        stats = self.dm_assistant.orchestrator.get_message_statistics()
        status += f"\n📊 MESSAGE BUS:\n"
        status += f"  • Total Messages: {stats['total_messages']}\n"
        status += f"  • Queue Size: {stats['queue_size']}\n"
        status += f"  • Registered Agents: {stats['registered_agents']}\n"
        
        # Cache status
        if self.dm_assistant.enable_caching and self.dm_assistant.cache_manager:
            cache_stats = self.dm_assistant.cache_manager.get_stats()
            status += f"\n💾 CACHE:\n"
            status += f"  • Total Items: {cache_stats['total_items']}\n"
            status += f"  • Memory Usage: {cache_stats['memory_usage_estimate']} chars\n"
        
        return status
    
    # Helper methods for formatting responses
    def _format_campaign_info(self, campaign: Dict[str, Any]) -> str:
        """Format campaign information for display."""
        info = f"📖 CAMPAIGN: {campaign['title']}\n"
        info += f"🎭 Theme: {campaign['theme']}\n"
        info += f"🗺️ Setting: {campaign['setting']}\n"
        info += f"📊 Level Range: {campaign['level_range']}\n\n"
        info += f"📝 Overview:\n{campaign['overview']}\n"
        return info
    
    def _format_player_list(self, players: List[Dict[str, Any]]) -> str:
        """Format player list for display."""
        if not players:
            return "❌ No players found. Check docs/players directory for character files."
        
        info = f"👥 PLAYERS ({len(players)}):\n\n"
        for i, player in enumerate(players, 1):
            info += f"  {i}. {player['name']} ({player['race']} {player['character_class']} Level {player['level']}) - HP: {player['hp']}\n"
        
        return info
    
    def _format_combat_status(self, combat_status: Dict[str, Any]) -> str:
        """Format combat status for display."""
        output = f"⚔️ **Combat Status** (Round {combat_status['round']})\n\n"
        
        for combatant in combat_status["combatants"]:
            marker = "👉 " if combatant["is_current"] else "   "
            alive = "💀" if not combatant["is_alive"] else ""
            output += f"{marker}{combatant['name']} - HP: {combatant['hp']}, AC: {combatant['ac']} {alive}\n"
        
        return output
    
    def _format_inventory(self, inventory: Dict[str, Any]) -> str:
        """Format inventory for display."""
        output = f"🎒 **INVENTORY**\n\n"
        
        items = inventory.get("items", [])
        if items:
            for item in items:
                output += f"• {item['name']} (x{item['quantity']})\n"
        else:
            output += "No items in inventory."
        
        return output
    
    def _extract_and_store_options(self, scenario_text: str):
        """Extract numbered options from scenario text and store them."""
        options = []
        lines = scenario_text.split('\n')
        
        # Look for numbered options
        patterns = [
            r'^\s*\*\*(\d+)\.\s*(.*?)\*\*\s*-?\s*(.*?)$',  # **1. Title** - description
            r'^\s*(\d+)\.\s*\*\*(.*?)\*\*\s*-\s*(.*?)$',  # 1. **Title** - description
            r'^\s*\*\*(\d+)\.\s*(.*?):\*\*\s*(.*?)$',      # **1. Title:** description
            r'^\s*(\d+)\.\s*(.*?)$'                         # Simple 1. description
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        num, title, description = groups
                        if description.strip():
                            options.append(f"{num}. {title.strip()} - {description.strip()}")
                        else:
                            options.append(f"{num}. {title.strip()}")
                    elif len(groups) == 2:
                        num, description = groups
                        options.append(f"{num}. {description.strip()}")
                    break
        
        self.last_scenario_options = options
    
    def _select_player_option(self, option_number: int) -> str:
        """Handle player option selection with refactored RAG-first generator."""
        if not self.last_scenario_options:
            return "❌ No options available. Please generate a scenario first."
        
        if option_number < 1 or option_number > len(self.last_scenario_options):
            return f"❌ Invalid option number. Please choose 1-{len(self.last_scenario_options)}"
        
        selected_option = self.last_scenario_options[option_number - 1]
        
        # Process the choice using refactored scenario generator with proper format
        response = self._send_message_and_wait_safe("scenario_generator", "apply_player_choice", {
            "game_state": {
                "current_options": "\n".join(self.last_scenario_options),
                "story_arc": self._get_current_campaign_context()
            },
            "player": "DM",
            "choice": option_number
        }, timeout=15.0)  # Increased timeout for LLM-based consequence generation
        
        if response and response.get("success"):
            continuation = response.get("continuation", "Option processed")
            self.last_scenario_options = []  # Clear options after selection
            return f"✅ **SELECTED:** Option {option_number}\n\n🎭 **STORY CONTINUES:**\n{continuation}"
        else:
            return f"❌ Failed to process option: {response.get('error', 'Unknown error')}"
    
    def _extract_params(self, instruction: str) -> dict:
        """Extract parameters from instruction."""
        words = instruction.split()
        params = {}
        
        # Basic parameter extraction
        if len(words) >= 3:
            params['param_1'] = words[2]
        if len(words) >= 4:
            params['param_2'] = words[3]
        
        return params
    
    def _is_condition_query(self, instruction_lower: str) -> bool:
        """Determine if the instruction is asking about D&D conditions."""
        conditions = ["blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
                     "invisible", "paralyzed", "poisoned", "prone", "restrained", "stunned", "unconscious"]
        
        # Check for condition queries
        for condition in conditions:
            if (f"{condition} condition" in instruction_lower or
                f"what happens when {condition}" in instruction_lower or
                f"happens when {condition}" in instruction_lower or
                (condition in instruction_lower and "condition" in instruction_lower)):
                return True
        
        return False
    
    def _is_scenario_request(self, instruction_lower: str) -> bool:
        """Determine if the instruction is requesting scenario generation."""
        scenario_keywords = [
            'generate', 'scenario', 'create', 'encounter', 'adventure',
            'story', 'quest', 'mission', 'situation', 'scene',
            'tavern', 'dungeon', 'forest', 'cave', 'castle',
            'bandits', 'goblins', 'dragon', 'combat', 'fight',
            'mysterious', 'ancient', 'dark', 'haunted',
            'village', 'town', 'city', 'crossroads'
        ]
        
        # Check if any scenario keywords are present
        if any(keyword in instruction_lower for keyword in scenario_keywords):
            # But exclude if it's clearly a rule query or other command
            exclude_patterns = [
                'rule', 'how does', 'what happens when', 'explain',
                'roll', 'dice', 'save game', 'load game', 'status'
            ]
            if not any(pattern in instruction_lower for pattern in exclude_patterns):
                return True
        
        return False
    
    def _get_current_campaign_context(self) -> str:
        """Get current campaign context for scenario generation."""
        # This could be enhanced to retrieve actual campaign context from campaign manager
        try:
            response = self._send_message_and_wait_safe("campaign_manager", "get_campaign_info", {}, timeout=2.0)
            if response and response.get("success"):
                campaign = response.get("campaign", {})
                return f"{campaign.get('title', 'Unknown Campaign')} - {campaign.get('theme', 'No theme')}"
        except:
            pass
        return "Default Campaign Context"
    
    def _get_current_game_state_for_scenarios(self) -> str:
        """Get simplified game state for scenario generation."""
        # This could be enhanced to retrieve actual game state
        try:
            response = self._send_message_and_wait_safe("game_engine", "get_game_state", {}, timeout=2.0)
            if response and response.get("success"):
                game_state = response.get("game_state", {})
                return f"Phase: {game_state.get('current_phase', 'exploration')}, Location: {game_state.get('current_location', 'unknown')}"
        except:
            pass
        return "Default game state"
