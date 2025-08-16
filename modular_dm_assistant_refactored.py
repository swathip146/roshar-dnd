"""
Modular RAG-Powered Dungeon Master Assistant
Main class that orchestrates the D&D assistant system
"""
import json
import time
import asyncio
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from agent_framework import AgentOrchestrator, MessageType
from agents.game_engine import GameEngineAgent, JSONPersister
from agents.npc_controller import NPCControllerAgent
from agents.scenario_generator import ScenarioGeneratorAgent
from agents.campaign_management import CampaignManagerAgent
from agents.haystack_pipeline_agent import HaystackPipelineAgent
from agents.dice_system import DiceSystemAgent, DiceRoller
from agents.combat_engine import CombatEngineAgent, CombatEngine
from agents.rule_enforcement_agent import RuleEnforcementAgent
from agents.character_manager_agent import CharacterManagerAgent
from agents.session_manager_agent import SessionManagerAgent
from agents.inventory_manager_agent import InventoryManagerAgent
from agents.spell_manager_agent import SpellManagerAgent
from agents.experience_manager_agent import ExperienceManagerAgent

# Import extracted helper classes
from narrative_tracker import NarrativeContinuityTracker
from cache_manager import SimpleInlineCache
from command_processor import CommandProcessor

# Claude-specific imports for text processing
CLAUDE_AVAILABLE = True


class ModularDMAssistant:
    """
    Main Modular DM Assistant class
    Focuses on core responsibilities: user interaction, agent orchestration, and system coordination
    """
    
    def __init__(self,
                 collection_name: str = "dnd_documents",
                 campaigns_dir: str = "resources/current_campaign",
                 players_dir: str = "docs/players",
                 verbose: bool = False,
                 enable_game_engine: bool = True,
                 tick_seconds: float = 0.8,
                 enable_caching: bool = True,
                 enable_async: bool = True,
                 game_save_file: Optional[str] = None):
        """Initialize the modular DM assistant"""
        
        # Configuration
        self.collection_name = collection_name
        self.campaigns_dir = campaigns_dir
        self.players_dir = players_dir
        self.verbose = verbose
        self.enable_game_engine = enable_game_engine
        self.tick_seconds = tick_seconds
        self.has_llm = CLAUDE_AVAILABLE
        self.enable_caching = enable_caching
        self.enable_async = enable_async
        
        # Game save functionality
        self.game_saves_dir = "./game_saves"
        self.current_save_file = game_save_file
        self.game_save_data = {}
        
        # Ensure game saves directory exists
        os.makedirs(self.game_saves_dir, exist_ok=True)
        
        # Initialize helper classes
        self.cache_manager = SimpleInlineCache() if enable_caching else None
        self.command_processor = CommandProcessor()
        self.narrative_tracker = NarrativeContinuityTracker() if enable_caching else None
        
        # Agent orchestrator
        self.orchestrator = AgentOrchestrator()
        
        # Initialize all D&D agents through the orchestrator
        self.orchestrator.initialize_dnd_agents(
            collection_name=collection_name,
            campaigns_dir=campaigns_dir,
            players_dir=players_dir,
            verbose=verbose,
            enable_game_engine=enable_game_engine,
            tick_seconds=tick_seconds
        )
        
        # Get agent references from orchestrator
        self.haystack_agent = self.orchestrator.haystack_agent
        self.campaign_agent = self.orchestrator.campaign_agent
        self.game_engine_agent = self.orchestrator.game_engine_agent
        self.npc_agent = self.orchestrator.npc_agent
        self.scenario_agent = self.orchestrator.scenario_agent
        self.dice_agent = self.orchestrator.dice_agent
        self.combat_agent = self.orchestrator.combat_agent
        self.rule_agent = self.orchestrator.rule_agent
        self.character_agent = self.orchestrator.character_agent
        self.session_agent = self.orchestrator.session_agent
        self.inventory_agent = self.orchestrator.inventory_agent
        self.spell_agent = self.orchestrator.spell_agent
        self.experience_agent = self.orchestrator.experience_agent
        
        # Game state tracking
        self.game_state = {}
        self.last_command = ""
        self.last_scenario_options = []
        
        # Load game save if specified
        if self.current_save_file:
            self._load_game_save(self.current_save_file)
        
        if self.verbose:
            print("🚀 Modular DM Assistant initialized successfully")
            if self.current_save_file:
                print(f"💾 Loaded game save: {self.current_save_file}")
            self._print_system_status()
    
    def _print_system_status(self):
        """Print status of system components"""
        print("\n🔧 SYSTEM STATUS:")
        print(f"  • Caching: {'✅ Enabled' if self.enable_caching else '❌ Disabled'}")
        print(f"  • Async Processing: {'✅ Enabled' if self.enable_async else '❌ Disabled'}")
        print(f"  • Game Engine: {'✅ Enabled' if self.enable_game_engine else '❌ Disabled'}")
        
        # Show cache statistics
        if self.enable_caching and self.cache_manager:
            cache_stats = self.cache_manager.get_stats()
            print(f"  • Cache: {cache_stats['total_items']} items")
        print()
    
    def start(self):
        """Start the orchestrator and all agents"""
        try:
            self.orchestrator.start()
            if self.verbose:
                print("🚀 Agent orchestrator started")
                stats = self.orchestrator.get_message_statistics()
                print(f"📊 Message bus active with {stats['registered_agents']} agents")
                
                # Brief pause to allow agents to fully initialize
                time.sleep(0.2)
                
                # Print agent status after they've started
                self._print_agent_status()
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to start orchestrator: {e}")
            raise
    
    def stop(self):
        """Stop the orchestrator and all agents"""
        try:
            self.orchestrator.stop()
            if self.verbose:
                print("⏹️ Agent orchestrator stopped")
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to stop orchestrator: {e}")
    
    def _print_agent_status(self):
        """Print status of all registered agents"""
        status = self.orchestrator.get_agent_status()
        print("\n🎭 AGENT STATUS:")
        for agent_id, info in status.items():
            running_status = "🟢 Running" if info["running"] else "🔴 Stopped"
            print(f"  • {agent_id} ({info['agent_type']}): {running_status}")
            if info["handlers"]:
                handlers_display = ', '.join(info['handlers'][:3])
                if len(info['handlers']) > 3:
                    handlers_display += f"... (+{len(info['handlers']) - 3} more)"
                print(f"    Handlers: {handlers_display}")
        print()
    
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction using the command processor"""
        instruction_lower = instruction.lower().strip()
        
        # Handle help command directly
        if instruction_lower == "help":
            return self.command_processor.get_command_help()
        
        # Handle numeric input for campaign selection
        if self.command_processor.is_numeric_selection(instruction, self.last_command):
            campaign_idx = self.command_processor.get_numeric_selection(instruction)
            response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
            self.last_command = ""
            if response and response.get("success"):
                return f"✅ Selected campaign: {response['campaign']}"
            else:
                return f"❌ {response.get('error', 'Failed to select campaign')}"
        
        # Parse command using command processor
        agent_id, action, params = self.command_processor.parse_command(instruction)
        
        if agent_id == "help":
            return self.command_processor.get_command_help()
        elif agent_id and action:
            return self._route_command(agent_id, action, instruction, params)
        
        # Fallback to general query
        return self._handle_general_query(instruction)
    
    def _route_command(self, agent_id: str, action: str, instruction: str, params: dict) -> str:
        """Route command to appropriate agent"""
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
                return self._handle_scenario_generation(instruction)
            elif agent_id == 'scenario_generator':
                return self._handle_scenario_command(action, params)
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
            if self.verbose:
                print(f"❌ Error routing command: {e}")
            return f"❌ Error processing command: {str(e)}"
    
    def _check_agent_availability(self, agent_id: str, action: str) -> bool:
        """Check if agent is registered and has the required handler"""
        try:
            agent_status = self.orchestrator.get_agent_status()
            if agent_id not in agent_status:
                return False
            
            if not agent_status[agent_id].get("running", False):
                return False
            
            handlers = agent_status[agent_id].get("handlers", [])
            if action not in handlers:
                return False
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error checking agent availability: {e}")
            return False
    
    def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Send a message to an agent and wait for response"""
        try:
            # Check cache if enabled
            cache_key = None
            if self.enable_caching and self.cache_manager and self._should_cache(agent_id, action, data):
                cache_key = f"{agent_id}_{action}_{json.dumps(data, sort_keys=True)}"
                cached_result = self.cache_manager.get(cache_key)
                if cached_result:
                    if self.verbose:
                        print(f"📦 Cache hit for {agent_id}:{action}")
                    return cached_result
            
            # Send message through orchestrator
            message_id = self.orchestrator.send_message_to_agent(agent_id, action, data)
            if not message_id:
                return {"success": False, "error": "Failed to send message"}
            
            # Wait for response
            start_time = time.time()
            result = None
            
            while time.time() - start_time < timeout:
                try:
                    history = self.orchestrator.message_bus.get_message_history(limit=50)
                    for msg in reversed(history):
                        if (msg.get("response_to") == message_id and
                            msg.get("message_type") == "response"):
                            result = msg.get("data", {})
                            break
                    
                    if result:
                        break
                    
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Error checking message history: {e}")
                
                time.sleep(0.1)
            
            # Cache result if successful
            if result and cache_key and self.cache_manager:
                ttl_hours = self._get_cache_ttl(agent_id, action)
                self.cache_manager.set(cache_key, result, ttl_hours)
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error sending message to {agent_id}:{action}: {e}")
            return {"success": False, "error": f"Communication error: {str(e)}"}
    
    def _should_cache(self, agent_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Determine if a query should be cached"""
        # Don't cache dice rolls or random content
        if agent_id == 'dice_system':
            return False
        
        # Don't cache scenario generation (creative content)
        if agent_id == 'haystack_pipeline' and action == 'query_scenario':
            return False
        
        # Don't cache if data contains random/time-sensitive elements
        query_text = json.dumps(data).lower()
        if any(keyword in query_text for keyword in ['roll', 'random', 'dice', 'turn', 'timestamp']):
            return False
        
        return True
    
    def _get_cache_ttl(self, agent_id: str, action: str) -> float:
        """Get cache TTL (time-to-live) in hours for different agent/action combinations"""
        if agent_id == 'rule_enforcement':
            return 24.0  # Rule queries can be cached longer
        elif agent_id == 'campaign_manager':
            return 12.0  # Campaign info can be cached for medium duration
        else:
            return 6.0   # General queries use shorter TTL
    
    # Command handler methods (simplified versions)
    def _handle_campaign_command(self, action: str, params: dict) -> str:
        """Handle campaign-related commands"""
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
        """Handle combat-related commands"""
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
        """Handle dice rolling commands"""
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
        """Handle rule checking commands"""
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
        """Handle game engine commands"""
        if action == 'list_saves':
            saves = self._list_game_saves()
            if not saves:
                return "❌ No game saves found"
            
            output = "💾 AVAILABLE GAME SAVES:\n\n"
            for i, save in enumerate(saves, 1):
                output += f"  {i}. **{save['save_name']}** - {save['campaign']} ({save['last_modified']})\n"
            
            output += "\n💡 *Type 'load save [number]' to load a specific save*"
            return output
        
        return f"❌ Unknown game engine action: {action}"
    
    def _handle_scenario_generation(self, instruction: str) -> str:
        """Handle scenario generation"""
        response = self._send_message_and_wait("haystack_pipeline", "query_scenario", {
            "query": instruction,
            "campaign_context": "",
            "game_state": ""
        })
        
        if response and response.get("success"):
            result = response["result"]
            scenario_text = result.get("answer", "Failed to generate scenario")
            
            # Extract and store options
            self._extract_and_store_options(scenario_text)
            
            return f"🎭 SCENARIO:\n{scenario_text}\n\n📝 *Type 'select option [number]' to choose a player option.*"
        else:
            return f"❌ Failed to generate scenario: {response.get('error', 'Unknown error')}"
    
    def _handle_scenario_command(self, action: str, params: dict) -> str:
        """Handle scenario-related commands"""
        if action == 'apply_player_choice':
            option_number = params.get('option_number', 1)
            return self._select_player_option(option_number)
        
        return f"❌ Unknown scenario action: {action}"
    
    def _handle_session_command(self, action: str, params: dict) -> str:
        """Handle session-related commands"""
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
        """Handle inventory-related commands"""
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
        """Handle spell-related commands"""
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
        """Handle character-related commands"""
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
        """Handle experience-related commands"""
        if action == 'level_up':
            response = self._send_message_and_wait("experience_manager", "level_up", {
                "character": params.get('param_1', '')
            })
            if response and response.get("success"):
                return f"⬆️ **LEVEL UP!**\n{response['message']}"
            else:
                return f"❌ Failed to level up: {response.get('error', 'Unknown error')}"
        
        return f"❌ Unknown experience action: {action}"
    
    def _handle_general_query(self, instruction: str) -> str:
        """Handle general queries using RAG"""
        response = self._send_message_and_wait("haystack_pipeline", "query_rag", {"query": instruction})
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            return f"💡 {answer}"
        else:
            return f"❌ Failed to process query: {response.get('error', 'Unknown error')}"
    
    def _get_system_status(self) -> str:
        """Get comprehensive system status"""
        status = "🤖 MODULAR DM ASSISTANT STATUS:\n\n"
        
        # Agent status
        agent_status = self.orchestrator.get_agent_status()
        status += "🎭 AGENT STATUS:\n"
        for agent_id, info in agent_status.items():
            running_status = "🟢 Running" if info["running"] else "🔴 Stopped"
            status += f"  • {agent_id} ({info['agent_type']}): {running_status}\n"
        
        # Message bus statistics
        stats = self.orchestrator.get_message_statistics()
        status += f"\n📊 MESSAGE BUS:\n"
        status += f"  • Total Messages: {stats['total_messages']}\n"
        status += f"  • Queue Size: {stats['queue_size']}\n"
        status += f"  • Registered Agents: {stats['registered_agents']}\n"
        
        # Cache status
        if self.enable_caching and self.cache_manager:
            cache_stats = self.cache_manager.get_stats()
            status += f"\n💾 CACHE:\n"
            status += f"  • Total Items: {cache_stats['total_items']}\n"
            status += f"  • Memory Usage: {cache_stats['memory_usage_estimate']} chars\n"
        
        return status
    
    # Helper methods for formatting responses
    def _format_campaign_info(self, campaign: Dict[str, Any]) -> str:
        """Format campaign information for display"""
        info = f"📖 CAMPAIGN: {campaign['title']}\n"
        info += f"🎭 Theme: {campaign['theme']}\n"
        info += f"🗺️ Setting: {campaign['setting']}\n"
        info += f"📊 Level Range: {campaign['level_range']}\n\n"
        info += f"📝 Overview:\n{campaign['overview']}\n"
        return info
    
    def _format_player_list(self, players: List[Dict[str, Any]]) -> str:
        """Format player list for display"""
        if not players:
            return "❌ No players found. Check docs/players directory for character files."
        
        info = f"👥 PLAYERS ({len(players)}):\n\n"
        for i, player in enumerate(players, 1):
            info += f"  {i}. {player['name']} ({player['race']} {player['character_class']} Level {player['level']}) - HP: {player['hp']}\n"
        
        return info
    
    def _format_combat_status(self, combat_status: Dict[str, Any]) -> str:
        """Format combat status for display"""
        output = f"⚔️ **Combat Status** (Round {combat_status['round']})\n\n"
        
        for combatant in combat_status["combatants"]:
            marker = "👉 " if combatant["is_current"] else "   "
            alive = "💀" if not combatant["is_alive"] else ""
            output += f"{marker}{combatant['name']} - HP: {combatant['hp']}, AC: {combatant['ac']} {alive}\n"
        
        return output
    
    def _format_inventory(self, inventory: Dict[str, Any]) -> str:
        """Format inventory for display"""
        output = f"🎒 **INVENTORY**\n\n"
        
        items = inventory.get("items", [])
        if items:
            for item in items:
                output += f"• {item['name']} (x{item['quantity']})\n"
        else:
            output += "No items in inventory."
        
        return output
    
    def _extract_and_store_options(self, scenario_text: str):
        """Extract numbered options from scenario text and store them"""
        import re
        
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
        """Handle player option selection"""
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
    
    def _list_game_saves(self) -> List[Dict[str, Any]]:
        """List all available game save files"""
        saves = []
        try:
            if not os.path.exists(self.game_saves_dir):
                return saves
            
            for filename in os.listdir(self.game_saves_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.game_saves_dir, filename)
                    try:
                        mod_time = os.path.getmtime(filepath)
                        mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
                        
                        with open(filepath, 'r') as f:
                            save_data = json.load(f)
                        
                        saves.append({
                            'filename': filename,
                            'save_name': save_data.get('save_name', filename[:-5]),
                            'campaign': save_data.get('campaign_info', {}).get('title', 'Unknown Campaign'),
                            'last_modified': mod_date
                        })
                    except (json.JSONDecodeError, IOError):
                        continue
            
            saves.sort(key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error listing game saves: {e}")
        
        return saves
    
    def _load_game_save(self, save_file: str) -> bool:
        """Load a game save file"""
        try:
            filepath = os.path.join(self.game_saves_dir, save_file)
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r') as f:
                self.game_save_data = json.load(f)
            
            # Restore game state to game engine
            if self.game_engine_agent and self.game_save_data.get('game_state'):
                self._send_message_and_wait("game_engine", "update_game_state", {
                    "updates": self.game_save_data['game_state']
                })
            
            # Restore last scenario options
            if self.game_save_data.get('last_scenario_options'):
                self.last_scenario_options = self.game_save_data['last_scenario_options']
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error loading save file {save_file}: {e}")
            return False
    
    def run_interactive(self):
        """Run the interactive DM assistant"""
        print("=== Modular RAG-Powered Dungeon Master Assistant ===")
        print("🤖 Using Agent Framework with Haystack Pipelines")
        print("Type 'help' for commands or 'quit' to exit")
        print()
        
        # Start the orchestrator
        self.start()
        
        try:
            while True:
                try:
                    dm_input = input("\nDM> ").strip()
                    
                    if dm_input.lower() in ["quit", "exit", "q"]:
                        break
                    
                    if not dm_input:
                        continue
                    
                    response = self.process_dm_input(dm_input)
                    print(response)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
        
        finally:
            # Stop the orchestrator
            self.stop()
            print("\n👋 Goodbye! All agents stopped.")


def main():
    """Main function to run the modular DM assistant"""
    try:
        # Get configuration from user
        collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
        if not collection_name:
            collection_name = "dnd_documents"
        
        # Check for existing game saves
        game_saves_dir = "./game_saves"
        game_save_file = None
        
        if os.path.exists(game_saves_dir):
            saves = []
            for filename in os.listdir(game_saves_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(game_saves_dir, filename)
                    try:
                        mod_time = os.path.getmtime(filepath)
                        mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
                        
                        with open(filepath, 'r') as f:
                            save_data = json.load(f)
                        
                        saves.append({
                            'filename': filename,
                            'save_name': save_data.get('save_name', filename[:-5]),
                            'campaign': save_data.get('campaign_info', {}).get('title', 'Unknown'),
                            'last_modified': mod_date,
                        })
                    except (json.JSONDecodeError, IOError):
                        continue
            
            saves.sort(key=lambda x: x['last_modified'], reverse=True)
            
            if saves:
                print("\n💾 EXISTING GAME SAVES FOUND:")
                print("0. Start New Campaign")
                for i, save in enumerate(saves, 1):
                    print(f"{i}. {save['save_name']} - {save['campaign']} ({save['last_modified']})")
                
                while True:
                    try:
                        choice = input(f"\nSelect option (0-{len(saves)}): ").strip()
                        if choice == "0":
                            print("🆕 Starting new campaign...")
                            break
                        elif choice.isdigit():
                            choice_num = int(choice)
                            if 1 <= choice_num <= len(saves):
                                selected_save = saves[choice_num - 1]
                                game_save_file = selected_save['filename']
                                print(f"📁 Loading save: {selected_save['save_name']}")
                                break
                        print(f"❌ Please enter a number between 0 and {len(saves)}")
                    except (ValueError, KeyboardInterrupt):
                        print("❌ Invalid input. Please enter a number.")
        
        assistant = ModularDMAssistant(
            collection_name=collection_name,
            verbose=True,
            game_save_file=game_save_file
        )
        
        assistant.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")


if __name__ == "__main__":
    main()
