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
            
            # Rule queries
            'rule': ('rule_enforcement', 'check_rule'),
            'check rule': ('rule_enforcement', 'check_rule'),
            'how does': ('rule_enforcement', 'check_rule'),
            'what happens': ('rule_enforcement', 'check_rule'),
            
            # Scenario generation
            'introduce scenario': ('scenario_generator', 'generate_with_context'),
            'generate scenario': ('scenario_generator', 'generate_with_context'),
            'create scenario': ('scenario_generator', 'generate_with_context'),
            'new scene': ('scenario_generator', 'generate_with_context'),
            'encounter': ('scenario_generator', 'generate_with_context'),
            'adventure': ('scenario_generator', 'generate_with_context'),
            'select option': ('scenario_generator', 'apply_player_choice'),
            'choose option': ('scenario_generator', 'apply_player_choice'),
            'option': ('scenario_generator', 'apply_player_choice'),
            
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
            
            # Rest mechanics
            'short rest': ('session_manager', 'take_short_rest'),
            'long rest': ('session_manager', 'take_long_rest'),
            'sleep': ('session_manager', 'take_long_rest'),
            
            # Inventory management
            'add item': ('inventory_manager', 'add_item'),
            'remove item': ('inventory_manager', 'remove_item'),
            'show inventory': ('inventory_manager', 'get_inventory'),
            'list items': ('inventory_manager', 'get_inventory'),
            
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
            'deceive': ('npc_controller', 'npc_social_interaction')
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
            
            # Player Management
            "list players": "Show all players",
            "player info [name]": "Show player details",
            "create character [name]": "Create new character",
            
            # Scenarios & Stories
            "generate scenario": "Create new story scenario",
            "select option [number]": "Choose story option",
            
            # Dice & Rules
            "roll [dice]": "Roll dice (e.g., 'roll 1d20', 'roll 3d6+2')",
            "rule [topic]": "Look up D&D rules",
            
            # Combat
            "start combat": "Begin combat encounter",
            "combat status": "Show initiative order",
            "next turn": "Advance to next combatant",
            "end combat": "Finish combat encounter",
            
            # Game Management
            "save game [name]": "Save current game state",
            "list saves": "Show available save files",
            
            # Character Features
            "short rest": "Take a short rest",
            "long rest": "Take a long rest",
            "show inventory": "Display character items",
            "cast [spell]": "Cast a spell"
        }
    
    def _get_command_help(self) -> str:
        """Return formatted help text for all available commands."""
        help_text = "🎮 AVAILABLE COMMANDS:\n\n"
        
        categories = {
            "📚 Campaign Management": [
                "list campaigns - Show available campaigns",
                "select campaign [number] - Choose a campaign",
                "campaign info - Show current campaign details"
            ],
            "👥 Player Management": [
                "list players - Show all players",
                "player info [name] - Show player details",
                "create character [name] - Create new character"
            ],
            "🎭 Scenarios & Stories": [
                "generate scenario - Create new story scenario",
                "select option [number] - Choose story option"
            ],
            "🎲 Dice & Rules": [
                "roll [dice] - Roll dice (e.g., 'roll 1d20', 'roll 3d6+2')",
                "rule [topic] - Look up D&D rules"
            ],
            "⚔️ Combat": [
                "start combat - Begin combat encounter",
                "combat status - Show initiative order",
                "next turn - Advance to next combatant",
                "end combat - Finish combat encounter"
            ],
            "💾 Game Management": [
                "save game [name] - Save current game state",
                "list saves - Show available save files"
            ],
            "🎒 Character Features": [
                "short rest - Take a short rest",
                "long rest - Take a long rest",
                "show inventory - Display character items",
                "cast [spell] - Cast a spell"
            ]
        }
        
        for category, commands in categories.items():
            help_text += f"{category}:\n"
            for command in commands:
                help_text += f"  • {command}\n"
            help_text += "\n"
        
        help_text += "💬 You can also ask any general D&D question for RAG-powered answers!"
        return help_text
    
    def _is_numeric_selection(self, instruction_lower: str) -> bool:
        """Check if instruction is a numeric selection."""
        return instruction_lower.isdigit() and self.last_command == "list_campaigns"
    
    def _handle_numeric_selection(self, instruction_lower: str) -> str:
        """Handle numeric campaign selection."""
        campaign_idx = int(instruction_lower) - 1
        response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
        self.last_command = ""
        if response and response.get("success"):
            return f"✅ Selected campaign: {response['campaign']}"
        else:
            return f"❌ {response.get('error', 'Failed to select campaign')}"
    
    def _parse_command(self, instruction: str) -> tuple:
        """Parse command into agent_id, action, and parameters."""
        instruction_lower = instruction.lower().strip()
        
        # Check for direct command matches
        for pattern, (agent, action) in self.command_map.items():
            if pattern in instruction_lower:
                params = self._extract_params(instruction)
                return agent, action, params
        
        # Handle special patterns with parameters
        if instruction_lower.startswith('roll '):
            return 'dice_system', 'roll_dice', {}
        elif instruction_lower.startswith('rule ') or 'how does' in instruction_lower or self._is_condition_query(instruction_lower):
            return 'rule_enforcement', 'check_rule', {}
        elif self._is_scenario_request(instruction_lower):
            return 'scenario_generator', 'generate_with_context', {}
        elif instruction_lower.startswith('select option'):
            match = re.search(r'select option (\d+)', instruction_lower)
            if match:
                return 'scenario_generator', 'apply_player_choice', {'option_number': int(match.group(1))}
        
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
                return self._handle_rule_query(instruction)
            elif agent_id == 'game_engine':
                return self._handle_game_engine_command(action, params)
            elif agent_id == 'haystack_pipeline':
                return self._handle_rag_query(instruction)
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
            response = self._send_message_and_wait("campaign_manager", "list_campaigns", {})
            if response:
                campaigns = response.get("campaigns", [])
                if campaigns:
                    self.last_command = "list_campaigns"
                    return "📚 AVAILABLE CAMPAIGNS:\n" + "\n".join(campaigns) + "\n\n💡 *Type the campaign number to select it*"
                else:
                    return "❌ No campaigns available. Check campaigns directory."
            return "❌ Failed to retrieve campaigns"
        
        elif action == 'get_campaign_info':
            response = self._send_message_and_wait("campaign_manager", "get_campaign_info", {})
            if response and response.get("success"):
                return self._format_campaign_info(response["campaign"])
            else:
                return f"❌ {response.get('error', 'No campaign selected')}"
        
        elif action == 'list_players':
            response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if response:
                return self._format_player_list(response.get("players", []))
            return "❌ Failed to retrieve players"
        
        return f"❌ Unknown campaign action: {action}"
    
    def _handle_combat_command(self, action: str, params: dict) -> str:
        """Handle combat-related commands."""
        if action == 'start_combat':
            # Add players to combat
            players_response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                for player in players_response["players"]:
                    self._send_message_and_wait("combat_engine", "add_combatant", {
                        "name": player["name"],
                        "max_hp": player.get("hp", 20),
                        "armor_class": player.get("combat_stats", {}).get("armor_class", 12),
                        "is_player": True
                    })
            
            # Start combat
            response = self._send_message_and_wait("combat_engine", "start_combat", {})
            if response and response.get("success"):
                return "⚔️ **COMBAT STARTED!**\n\nUse 'combat status' to see initiative order and 'next turn' to advance."
            else:
                return f"❌ Failed to start combat: {response.get('error', 'Unknown error')}"
        
        elif action == 'get_combat_status':
            response = self._send_message_and_wait("combat_engine", "get_combat_status", {})
            if response and response.get("success"):
                return self._format_combat_status(response["status"])
            else:
                return f"❌ Failed to get combat status: {response.get('error', 'Unknown error')}"
        
        elif action == 'next_turn':
            response = self._send_message_and_wait("combat_engine", "next_turn", {})
            if response and response.get("success"):
                current = response.get("current_combatant")
                if current:
                    return f"🔄 **Turn advanced!**\n🎯 **Now active:** {current['name']}"
                return "🔄 Turn advanced"
            else:
                return f"❌ Failed to advance turn: {response.get('error', 'Unknown error')}"
        
        elif action == 'end_combat':
            response = self._send_message_and_wait("combat_engine", "end_combat", {})
            if response and response.get("success"):
                return "🏁 **COMBAT ENDED!**"
            else:
                return f"❌ Failed to end combat: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown combat action: {action}"
    
    def _handle_dice_roll(self, instruction: str) -> str:
        """Handle dice rolling commands."""
        response = self._send_message_and_wait("dice_system", "roll_dice", {
            "expression": "1d20",  # Default, could be enhanced
            "context": "Manual roll",
            "skill": None
        })
        
        if response and response.get("success"):
            result = response["result"]
            return f"🎲 **DICE ROLL**\n**Result:** {result['description']}"
        else:
            return f"❌ Failed to roll dice: {response.get('error', 'Unknown error')}"
    
    def _handle_rule_query(self, instruction: str) -> str:
        """Handle rule checking commands."""
        response = self._send_message_and_wait("rule_enforcement", "check_rule", {
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
        
        return f"❌ Unknown game engine action: {action}"
    
    def _handle_rag_query(self, instruction: str) -> str:
        """Handle direct RAG queries (not scenario generation)."""
        response = self._send_message_and_wait("haystack_pipeline", "query_rag", {
            "query": instruction
        })
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            return f"💡 {answer}"
        else:
            return f"❌ Failed to process query: {response.get('error', 'Unknown error')}"
    
    def _handle_scenario_command(self, action: str, params: dict, instruction: str = "") -> str:
        """Handle scenario-related commands."""
        if action == 'apply_player_choice':
            option_number = params.get('option_number', 1)
            return self._select_player_option(option_number)
        elif action == 'generate_with_context':
            return self._handle_scenario_generation(instruction)
        
        return f"❌ Unknown scenario action: {action}"
    
    def _handle_scenario_generation(self, instruction: str) -> str:
        """Handle scenario generation using scenario generator agent."""
        response = self._send_message_and_wait("scenario_generator", "generate_with_context", {
            "query": instruction,
            "use_rag": True,
            "campaign_context": "",
            "game_state": ""
        })
        
        if response and response.get("success"):
            scenario = response.get("scenario", {})
            scenario_text = scenario.get("scenario_text", "Failed to generate scenario")
            options = scenario.get("options", [])
            
            # Store options for later selection
            if options:
                self.last_scenario_options = options
                options_text = "\n".join(options)
                return f"🎭 **SCENARIO:**\n{scenario_text}\n\n**OPTIONS:**\n{options_text}\n\n📝 *Type 'select option [number]' to choose a player option.*"
            else:
                return f"🎭 **SCENARIO:**\n{scenario_text}"
        else:
            return f"❌ Failed to generate scenario: {response.get('error', 'Unknown error')}"
    
    def _handle_session_command(self, action: str, params: dict) -> str:
        """Handle session-related commands."""
        if action == 'take_short_rest':
            response = self._send_message_and_wait("session_manager", "take_short_rest", {})
            if response and response.get("success"):
                return f"😴 **SHORT REST COMPLETED!**\n{response['message']}"
            else:
                return f"❌ Failed to take short rest: {response.get('error', 'Unknown error')}"
        
        elif action == 'take_long_rest':
            response = self._send_message_and_wait("session_manager", "take_long_rest", {})
            if response and response.get("success"):
                return f"🛌 **LONG REST COMPLETED!**\n{response['message']}"
            else:
                return f"❌ Failed to take long rest: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown session action: {action}"
    
    def _handle_inventory_command(self, action: str, params: dict) -> str:
        """Handle inventory-related commands."""
        if action == 'get_inventory':
            response = self._send_message_and_wait("inventory_manager", "get_inventory", {
                "character": params.get('param_1', 'party')
            })
            if response and response.get("success"):
                return self._format_inventory(response.get("inventory", {}))
            else:
                return f"❌ Failed to get inventory: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown inventory action: {action}"
    
    def _handle_spell_command(self, action: str, params: dict) -> str:
        """Handle spell-related commands."""
        if action == 'cast_spell':
            response = self._send_message_and_wait("spell_manager", "cast_spell", {
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
            response = self._send_message_and_wait("character_manager", "create_character", {
                "name": params.get('param_1', ''),
                "race": "Human",
                "character_class": "Fighter",
                "level": 1
            })
            if response and response.get("success"):
                return f"🎭 **CHARACTER CREATED!**\n{response['message']}"
            else:
                return f"❌ Failed to create character: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown character action: {action}"
    
    def _handle_experience_command(self, action: str, params: dict) -> str:
        """Handle experience-related commands."""
        if action == 'level_up':
            response = self._send_message_and_wait("experience_manager", "level_up", {
                "character": params.get('param_1', '')
            })
            if response and response.get("success"):
                return f"⬆️ **LEVEL UP!**\n{response['message']}"
            else:
                return f"❌ Failed to level up: {response.get('error', 'Unknown error')}"
        
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
        
        return f"❌ Unknown NPC action: {action}"

    def _handle_npc_dialogue(self, instruction: str, params: dict) -> str:
        """Handle NPC dialogue generation requests"""
        npc_name = params.get('param_1', '').strip()
        player_input = params.get('param_2', '').strip()
        
        if not npc_name:
            return "❌ Please specify NPC name. Usage: talk to npc [name] [optional: what to say]"
        
        response = self._send_message_and_wait("npc_controller", "generate_npc_dialogue", {
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
        response = self._send_message_and_wait("npc_controller", "generate_npc_behavior", {
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
        
        response = self._send_message_and_wait("npc_controller", "get_npc_state", {
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
        
        response = self._send_message_and_wait("npc_controller", "npc_social_interaction", {
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
        response = self._send_message_and_wait("haystack_pipeline", "query_rag", {"query": instruction})
        
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
        """Handle player option selection."""
        if not self.last_scenario_options:
            return "❌ No options available. Please generate a scenario first."
        
        if option_number < 1 or option_number > len(self.last_scenario_options):
            return f"❌ Invalid option number. Please choose 1-{len(self.last_scenario_options)}"
        
        selected_option = self.last_scenario_options[option_number - 1]
        
        # Process the choice using scenario generator
        response = self._send_message_and_wait("scenario_generator", "apply_player_choice", {
            "game_state": {"current_options": "\n".join(self.last_scenario_options)},
            "player": "DM",
            "choice": option_number
        })
        
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
