"""
Command Processor
Handles command parsing, routing, and processing for the D&D assistant
"""
import re
from typing import Dict, List, Any, Optional, Tuple


class CommandProcessor:
    """Processes and routes user commands to appropriate agents"""
    
    def __init__(self):
        # Command mapping dictionary
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
            'introduce scenario': ('haystack_pipeline', 'query_scenario'),
            'generate scenario': ('haystack_pipeline', 'query_scenario'),
            'create scenario': ('haystack_pipeline', 'query_scenario'),
            'new scene': ('haystack_pipeline', 'query_scenario'),
            'encounter': ('haystack_pipeline', 'query_scenario'),
            'adventure': ('haystack_pipeline', 'query_scenario'),
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
            'prepare spells': ('spell_manager', 'get_prepared_spells')
        }
    
    def get_command_help(self) -> str:
        """Return formatted help text for all available commands"""
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
    
    def parse_command(self, instruction: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """
        Parse user instruction and return (agent_id, action, params)
        Returns (None, None, {}) if no command match found
        """
        instruction_lower = instruction.lower().strip()
        
        # Handle help command directly
        if instruction_lower == "help":
            return "help", "help", {}
        
        # Handle system commands directly
        if instruction_lower in ["agent status", "system status"]:
            return "orchestrator", "get_agent_status", {}
        
        # Check for direct command matches
        for pattern, (agent, action) in self.command_map.items():
            if pattern in instruction_lower:
                params = self._extract_params(instruction)
                return agent, action, params
        
        # Handle special patterns with parameters
        if instruction_lower.startswith('roll '):
            return 'dice_system', 'roll_dice', {'instruction': instruction}
        elif instruction_lower.startswith('rule ') or 'how does' in instruction_lower or self._is_condition_query(instruction_lower):
            return 'rule_enforcement', 'check_rule', {'instruction': instruction}
        elif self._is_scenario_request(instruction_lower):
            return 'haystack_pipeline', 'query_scenario', {'instruction': instruction}
        elif instruction_lower.startswith('select option'):
            match = re.search(r'select option (\d+)', instruction_lower)
            if match:
                return 'scenario_generator', 'apply_player_choice', {'option_number': int(match.group(1))}
        
        # No command match found
        return None, None, {}
    
    def _extract_params(self, instruction: str) -> Dict[str, Any]:
        """Extract parameters from instruction"""
        words = instruction.split()
        params = {}
        
        # For commands like "save game MyGame" or "load save 1"
        if len(words) >= 3:
            params['param_1'] = words[2]
        
        return params
    
    def _is_condition_query(self, instruction_lower: str) -> bool:
        """Determine if the instruction is asking about D&D conditions"""
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
        """Determine if the instruction is requesting scenario generation"""
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
    
    def is_numeric_selection(self, instruction: str, last_command: str) -> bool:
        """Check if instruction is a numeric selection for a previous command"""
        if instruction.isdigit() and last_command == "list_campaigns":
            return True
        return False
    
    def get_numeric_selection(self, instruction: str) -> int:
        """Extract numeric selection from instruction"""
        return int(instruction) - 1  # Convert to 0-based index
