"""
Modular RAG-Powered Dungeon Master Assistant
Orchestrates multiple AI agents using the agent framework for enhanced D&D gameplay
"""
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

from agent_framework import AgentOrchestrator, MessageType
from game_engine import GameEngineAgent, JSONPersister
from npc_controller import NPCControllerAgent
from scenario_generator import ScenarioGeneratorAgent
from campaign_management import CampaignManagerAgent
from haystack_pipeline_agent import HaystackPipelineAgent
from rag_agent_integrated import create_rag_agent, RAGAgentFramework, RAGAgent
from dice_system import DiceSystemAgent, DiceRoller
from combat_engine import CombatEngineAgent, CombatEngine
from rule_enforcement_agent import RuleEnforcementAgent

# Claude-specific imports for text processing
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class ModularDMAssistant:
    """
    Modular DM Assistant that orchestrates multiple AI agents for comprehensive D&D management
    """
    
    def __init__(self,
                 collection_name: str = "dnd_documents",
                 campaigns_dir: str = "docs/current_campaign",
                 players_dir: str = "docs/players",
                 verbose: bool = False,
                 enable_game_engine: bool = True,
                 tick_seconds: float = 0.8):
        """Initialize the modular DM assistant"""
        
        self.collection_name = collection_name
        self.campaigns_dir = campaigns_dir
        self.players_dir = players_dir
        self.verbose = verbose
        self.enable_game_engine = enable_game_engine
        self.tick_seconds = tick_seconds
        self.has_llm = CLAUDE_AVAILABLE
        
        # Agent orchestrator
        self.orchestrator = AgentOrchestrator()
        
        # Agents
        self.haystack_agent: Optional[HaystackPipelineAgent] = None
        self.campaign_agent: Optional[CampaignManagerAgent] = None
        self.game_engine_agent: Optional[GameEngineAgent] = None
        self.npc_agent: Optional[NPCControllerAgent] = None
        self.scenario_agent: Optional[ScenarioGeneratorAgent] = None
        self.dice_agent: Optional[DiceSystemAgent] = None
        self.combat_agent: Optional[CombatEngineAgent] = None
        self.rule_agent: Optional[RuleEnforcementAgent] = None
        
        # Legacy RAG agent for compatibility
        self.rag_agent: Optional[RAGAgent] = None
        
        # Game state tracking
        self.game_state = {}
        self.last_command = ""
        
        # Initialize all components
        self._initialize_agents()
        
        if self.verbose:
            print("🤖 Modular DM Assistant initialized with agent framework")
            self._print_agent_status()
    
    def _initialize_agents(self):
        """Initialize and register all agents"""
        try:
            # 1. Initialize Haystack Pipeline Agent (core RAG services)
            self.haystack_agent = HaystackPipelineAgent(
                collection_name=self.collection_name,
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.haystack_agent)
            
            # 2. Initialize Campaign Manager Agent
            self.campaign_agent = CampaignManagerAgent(
                campaigns_dir=self.campaigns_dir,
                players_dir=self.players_dir
            )
            self.orchestrator.register_agent(self.campaign_agent)
            
            # 3. Initialize Game Engine Agent (if enabled)
            if self.enable_game_engine:
                persister = JSONPersister("./game_state_checkpoint.json")
                self.game_engine_agent = GameEngineAgent(
                    persister=persister,
                    tick_seconds=self.tick_seconds
                )
                self.orchestrator.register_agent(self.game_engine_agent)
            
            # 4. Initialize Dice System Agent
            self.dice_agent = DiceSystemAgent()
            self.orchestrator.register_agent(self.dice_agent)
            
            # 5. Initialize Combat Engine Agent
            dice_roller = DiceRoller()
            self.combat_agent = CombatEngineAgent(dice_roller)
            self.orchestrator.register_agent(self.combat_agent)
            
            # 6. Initialize legacy RAG agent for backward compatibility
            self.rag_agent = RAGAgent(
                collection_name=self.collection_name,
                verbose=self.verbose
            )
            
            # 7. Initialize Rule Enforcement Agent
            self.rule_agent = RuleEnforcementAgent(
                rag_agent=self.rag_agent,
                strict_mode=False
            )
            self.orchestrator.register_agent(self.rule_agent)
            
            # 8. Initialize NPC Controller Agent
            self.npc_agent = NPCControllerAgent(
                rag_agent=self.rag_agent,
                mode="hybrid"
            )
            self.orchestrator.register_agent(self.npc_agent)
            
            # 9. Initialize Scenario Generator Agent
            self.scenario_agent = ScenarioGeneratorAgent(
                rag_agent=self.rag_agent,
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.scenario_agent)
            
            if self.verbose:
                print("✅ All agents initialized successfully")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize agents: {e}")
            raise
    
    def _print_agent_status(self):
        """Print status of all registered agents"""
        status = self.orchestrator.get_agent_status()
        print("\n🎭 AGENT STATUS:")
        for agent_id, info in status.items():
            running_status = "🟢 Running" if info["running"] else "🔴 Stopped"
            print(f"  • {agent_id} ({info['agent_type']}): {running_status}")
            if info["handlers"]:
                print(f"    Handlers: {', '.join(info['handlers'][:3])}{'...' if len(info['handlers']) > 3 else ''}")
        print()
    
    def start(self):
        """Start the orchestrator and all agents"""
        try:
            self.orchestrator.start()
            if self.verbose:
                print("🚀 Agent orchestrator started")
                stats = self.orchestrator.get_message_statistics()
                print(f"📊 Message bus active with {stats['registered_agents']} agents")
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
    
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction and coordinate agent responses"""
        instruction_lower = instruction.lower().strip()
        
        # Handle simple numeric input for campaign selection
        if instruction.strip().isdigit() and self.last_command == "list_campaigns":
            campaign_idx = int(instruction.strip()) - 1
            response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
            self.last_command = ""
            if response and response.get("success"):
                return f"✅ Selected campaign: {response['campaign']}"
            else:
                return f"❌ {response.get('error', 'Failed to select campaign')}"
        
        # Campaign management commands
        if "list campaigns" in instruction_lower or "show campaigns" in instruction_lower:
            response = self._send_message_and_wait("campaign_manager", "list_campaigns", {})
            if response:
                campaigns = response.get("campaigns", [])
                if campaigns:
                    self.last_command = "list_campaigns"
                    return "📚 AVAILABLE CAMPAIGNS:\n" + "\n".join(campaigns) + "\n\n💡 *Type the campaign number to select it*"
                else:
                    return "❌ No campaigns available. Check campaigns directory."
            return "❌ Failed to retrieve campaigns"
        
        elif "select campaign" in instruction_lower:
            self.last_command = ""
            # Extract campaign number
            words = instruction.split()
            for word in words:
                if word.isdigit():
                    campaign_idx = int(word) - 1
                    response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
                    if response and response.get("success"):
                        return f"✅ Selected campaign: {response['campaign']}"
                    else:
                        return f"❌ {response.get('error', 'Failed to select campaign')}"
            
            # If no number found, show available campaigns
            response = self._send_message_and_wait("campaign_manager", "list_campaigns", {})
            if response:
                campaigns = response.get("campaigns", [])
                return f"❌ Please specify campaign number (1-{len(campaigns)})"
            return "❌ No campaigns available"
        
        elif "campaign info" in instruction_lower or "show campaign" in instruction_lower:
            self.last_command = ""
            response = self._send_message_and_wait("campaign_manager", "get_campaign_info", {})
            if response and response.get("success"):
                return self._format_campaign_info(response["campaign"])
            else:
                return f"❌ {response.get('error', 'No campaign selected')}"
        
        # Player management commands
        elif "list players" in instruction_lower or "show players" in instruction_lower:
            self.last_command = ""
            response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if response:
                return self._format_player_list(response.get("players", []))
            return "❌ Failed to retrieve players"
        
        elif "player info" in instruction_lower:
            self.last_command = ""
            # Extract player name
            words = instruction.split()
            player_name = None
            for i, word in enumerate(words):
                if word.lower() in ["info", "player"] and i + 1 < len(words):
                    player_name = words[i + 1]
                    break
            
            if player_name:
                response = self._send_message_and_wait("campaign_manager", "get_player_info", {"name": player_name})
                if response and response.get("success"):
                    return self._format_player_info(response["player"])
                else:
                    return f"❌ {response.get('error', 'Player not found')}"
            else:
                return "❌ Please specify player name. Usage: player info [name]"
        
        # Dice rolling commands
        elif any(keyword in instruction_lower for keyword in ["roll", "dice", "d20", "d6", "d8", "d10", "d12", "d4", "d100"]):
            self.last_command = ""
            return self._handle_dice_roll(instruction)
        
        # Combat commands
        elif any(keyword in instruction_lower for keyword in ["combat", "initiative", "attack", "damage", "heal", "condition"]):
            self.last_command = ""
            return self._handle_combat_command(instruction)
        
        # Rule checking commands
        elif any(keyword in instruction_lower for keyword in ["rule", "rules", "check rule", "how does", "what happens when"]):
            self.last_command = ""
            return self._handle_rule_query(instruction)
        
        # Scenario generation and game management
        elif any(keyword in instruction_lower for keyword in ["introduce scenario", "generate", "scenario", "scene", "encounter", "adventure"]):
            self.last_command = ""
            return self._generate_scenario(instruction)
        
        elif "select option" in instruction_lower:
            self.last_command = ""
            # Extract option number
            words = instruction.split()
            for word in words:
                if word.isdigit():
                    option_num = int(word)
                    return self._select_player_option(option_num)
            return "❌ Please specify option number (e.g., 'select option 2')"
        
        # Game engine commands
        elif "start engine" in instruction_lower:
            self.last_command = ""
            if self.game_engine_agent:
                return "✅ Game engine is managed automatically by the agent framework"
            else:
                return "❌ Game engine not available"
        
        elif "stop engine" in instruction_lower:
            self.last_command = ""
            return "ℹ️ Game engine lifecycle is managed by the agent framework"
        
        elif "engine status" in instruction_lower or "agent status" in instruction_lower:
            self.last_command = ""
            return self._get_system_status()
        
        # Game state commands
        elif "game state" in instruction_lower or "show state" in instruction_lower:
            self.last_command = ""
            if self.game_engine_agent:
                response = self._send_message_and_wait("game_engine", "get_game_state", {})
                if response and response.get("game_state"):
                    return f"📊 GAME STATE:\n{json.dumps(response['game_state'], indent=2)}"
            return "❌ Game state not available"
        
        # General queries - use RAG
        else:
            self.last_command = ""
            return self._handle_general_query(instruction)
    
    def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Send a message to an agent and wait for response"""
        try:
            # Send message through orchestrator
            message_id = self.orchestrator.send_message_to_agent(agent_id, action, data)
            
            # Wait for response in message history
            start_time = time.time()
            while time.time() - start_time < timeout:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and 
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                time.sleep(0.1)
            
            if self.verbose:
                print(f"⚠️ Timeout waiting for response from {agent_id}")
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error sending message to {agent_id}: {e}")
            return None
    
    def _format_campaign_info(self, campaign: Dict[str, Any]) -> str:
        """Format campaign information for display"""
        info = f"📖 CAMPAIGN: {campaign['title']}\n"
        info += f"🎭 Theme: {campaign['theme']}\n"
        info += f"🗺️ Setting: {campaign['setting']}\n"
        info += f"📊 Level Range: {campaign['level_range']}\n\n"
        info += f"📝 Overview:\n{campaign['overview']}\n\n"
        
        if campaign.get('npcs'):
            info += f"👥 Key NPCs ({len(campaign['npcs'])}):\n"
            for npc in campaign['npcs'][:3]:
                info += f"  • {npc['name']} ({npc['role']})\n"
            if len(campaign['npcs']) > 3:
                info += f"  ... and {len(campaign['npcs']) - 3} more\n"
            info += "\n"
        
        if campaign.get('locations'):
            info += f"📍 Locations ({len(campaign['locations'])}):\n"
            for loc in campaign['locations'][:3]:
                info += f"  • {loc['name']} ({loc['location_type']})\n"
            if len(campaign['locations']) > 3:
                info += f"  ... and {len(campaign['locations']) - 3} more\n"
        
        return info
    
    def _format_player_list(self, players: List[Dict[str, Any]]) -> str:
        """Format player list for display"""
        if not players:
            return "❌ No players found. Check docs/players directory for character files."
        
        info = f"👥 PLAYERS ({len(players)}):\n\n"
        for i, player in enumerate(players, 1):
            info += f"  {i}. {player['name']} ({player['race']} {player['character_class']} Level {player['level']}) - HP: {player['hp']}\n"
        
        return info
    
    def _format_player_info(self, player: Dict[str, Any]) -> str:
        """Format detailed player information"""
        info = f"👤 PLAYER: {player['name']}\n"
        info += f"🎭 Race: {player['race']}\n"
        info += f"⚔️ Class: {player['character_class']} (Level {player['level']})\n"
        info += f"📚 Background: {player['background']}\n"
        info += f"📖 Rulebook: {player['rulebook']}\n\n"
        
        # Combat stats
        if player.get('combat_stats'):
            info += "⚔️ COMBAT STATS:\n"
            for stat, value in player['combat_stats'].items():
                stat_name = stat.replace('_', ' ').title()
                info += f"  • {stat_name}: {value}\n"
            info += "\n"
        
        # Ability scores
        if player.get('ability_scores'):
            info += "📊 ABILITY SCORES:\n"
            for ability, score in player['ability_scores'].items():
                modifier = (score - 10) // 2
                modifier_str = f"+{modifier}" if modifier >= 0 else str(modifier)
                info += f"  • {ability.title()}: {score} ({modifier_str})\n"
            info += "\n"
        
        return info
    
    def _generate_scenario(self, user_query: str) -> str:
        """Generate scenario using the scenario agent"""
        # Get campaign context if available
        campaign_context = ""
        campaign_response = self._send_message_and_wait("campaign_manager", "get_campaign_context", {})
        if campaign_response and campaign_response.get("success"):
            campaign_context = json.dumps(campaign_response["context"])
        
        # Get current game state if available
        game_state = ""
        if self.game_engine_agent:
            state_response = self._send_message_and_wait("game_engine", "get_game_state", {})
            if state_response and state_response.get("game_state"):
                game_state = json.dumps(state_response["game_state"])
        
        # Generate scenario using Haystack pipeline (longer timeout for LLM processing)
        response = self._send_message_and_wait("haystack_pipeline", "query_scenario", {
            "query": user_query,
            "campaign_context": campaign_context,
            "game_state": game_state
        }, timeout=30.0)
        
        if response and response.get("success"):
            result = response["result"]
            scenario_text = result.get("answer", "Failed to generate scenario")
            
            return f"🎭 SCENARIO (Agent-Generated):\n{scenario_text}\n\n🤖 Generated using modular agent architecture\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to generate scenario: {error_msg}"
    
    def _select_player_option(self, option_number: int) -> str:
        """Handle player option selection via scenario agent"""
        if not self.game_engine_agent:
            return "❌ Game engine not available for option processing"
        
        # Get current game state
        state_response = self._send_message_and_wait("game_engine", "get_game_state", {})
        if not state_response or not state_response.get("game_state"):
            return "❌ Could not retrieve game state"
        
        game_state = state_response["game_state"]
        
        # Send choice to scenario agent (longer timeout for LLM processing)
        response = self._send_message_and_wait("scenario_generator", "apply_player_choice", {
            "game_state": game_state,
            "player": "DM",  # DM making the choice
            "choice": option_number
        }, timeout=30.0)
        
        if response and response.get("success"):
            continuation = response.get("continuation", "Option processed")
            return f"✅ **SELECTED:** Option {option_number}\n\n🎭 **STORY CONTINUES:**\n{continuation}\n\n📝 *Use 'generate scenario' to continue the adventure.*"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to process option: {error_msg}"
    
    def _get_system_status(self) -> str:
        """Get comprehensive system status"""
        status = "🤖 MODULAR DM ASSISTANT STATUS:\n\n"
        
        # Agent status
        agent_status = self.orchestrator.get_agent_status()
        status += "🎭 AGENTS:\n"
        for agent_id, info in agent_status.items():
            running = "🟢" if info["running"] else "🔴"
            status += f"  {running} {agent_id} ({info['agent_type']})\n"
        
        # Message bus statistics
        stats = self.orchestrator.get_message_statistics()
        status += f"\n📊 MESSAGE BUS:\n"
        status += f"  • Total Messages: {stats['total_messages']}\n"
        status += f"  • Queue Size: {stats['queue_size']}\n"
        status += f"  • Registered Agents: {stats['registered_agents']}\n"
        
        # RAG system status
        if self.haystack_agent:
            rag_response = self._send_message_and_wait("haystack_pipeline", "get_pipeline_status", {})
            if rag_response:
                status += f"\n🔍 RAG SYSTEM:\n"
                status += f"  • LLM Available: {'✅' if rag_response.get('has_llm') else '❌'}\n"
                status += f"  • Collection: {rag_response.get('collection', 'Unknown')}\n"
                pipelines = rag_response.get('pipelines', {})
                for name, available in pipelines.items():
                    status += f"  • {name.title()} Pipeline: {'✅' if available else '❌'}\n"
        
        # Combat system status
        if self.combat_agent:
            combat_response = self._send_message_and_wait("combat_engine", "get_combat_status", {})
            if combat_response and combat_response.get("success"):
                combat_status = combat_response["status"]
                status += f"\n⚔️ COMBAT SYSTEM:\n"
                status += f"  • State: {combat_status['state'].title()}\n"
                if combat_status['state'] == 'active':
                    status += f"  • Round: {combat_status['round']}\n"
                    status += f"  • Combatants: {len(combat_status['combatants'])}\n"
                    current = combat_status.get('current_combatant')
                    if current:
                        status += f"  • Current Turn: {current['name']}\n"
        
        # Dice system status
        if self.dice_agent:
            history_response = self._send_message_and_wait("dice_system", "get_roll_history", {"limit": 1})
            if history_response and history_response.get("success"):
                history = history_response.get("history", [])
                status += f"\n🎲 DICE SYSTEM:\n"
                status += f"  • Status: ✅ Active\n"
                status += f"  • Recent Rolls: {len(history)}\n"
                if history:
                    last_roll = history[0]
                    status += f"  • Last Roll: {last_roll['expression']} = {last_roll['total']}\n"
        
        return status
    
    def _handle_general_query(self, query: str) -> str:
        """Handle general queries using RAG"""
        response = self._send_message_and_wait("haystack_pipeline", "query_rag", {"query": query}, timeout=30.0)
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            sources = result.get("sources", [])
            
            output = f"💡 ANSWER:\n{answer}"
            
            if sources:
                output += f"\n\n📚 SOURCES ({len(sources)}):"
                for source in sources[:3]:  # Show top 3 sources
                    output += f"\n  • {source['source']} (Score: {source['score']})"
                if len(sources) > 3:
                    output += f"\n  ... and {len(sources) - 3} more sources"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to process query: {error_msg}"
    
    def _handle_dice_roll(self, instruction: str) -> str:
        """Handle dice rolling commands"""
        import re
        
        # Extract dice expression from instruction
        dice_patterns = [
            r'\b(\d*d\d+(?:[kKhHlL]\d+)?(?:[+-]\d+)?(?:\s+(?:adv|advantage|dis|disadvantage))?)\b',
            r'\b(d\d+)\b',  # Simple d20, d6, etc.
            r'\b(\d+d\d+)\b'  # 3d6, 2d8, etc.
        ]
        
        dice_expression = None
        for pattern in dice_patterns:
            match = re.search(pattern, instruction, re.IGNORECASE)
            if match:
                dice_expression = match.group(1)
                break
        
        # If no specific dice found, try to infer from context
        if not dice_expression:
            if any(word in instruction.lower() for word in ['attack', 'hit']):
                dice_expression = "1d20"
            elif any(word in instruction.lower() for word in ['damage', 'hurt']):
                dice_expression = "1d6"
            elif any(word in instruction.lower() for word in ['stats', 'ability', 'score']):
                dice_expression = "4d6k3"
            else:
                dice_expression = "1d20"  # Default
        
        # Add context from instruction
        context = "Manual roll"
        if "attack" in instruction.lower():
            context = "Attack roll"
        elif "damage" in instruction.lower():
            context = "Damage roll"
        elif "save" in instruction.lower() or "saving" in instruction.lower():
            context = "Saving throw"
        elif any(skill in instruction.lower() for skill in ['stealth', 'perception', 'insight', 'persuasion', 'deception', 'athletics', 'acrobatics']):
            context = "Skill check"
        
        # Send to dice agent
        response = self._send_message_and_wait("dice_system", "roll_dice", {
            "expression": dice_expression,
            "context": context
        })
        
        if response and response.get("success"):
            result = response["result"]
            output = f"🎲 **{context.upper()}**\n"
            output += f"**Expression:** {result['expression']}\n"
            output += f"**Result:** {result['description']}\n"
            
            if result.get('critical_hit'):
                output += "🔥 **CRITICAL HIT!**\n"
            elif result.get('critical_fail'):
                output += "💥 **CRITICAL FAILURE!**\n"
            
            if result['advantage_type'] != 'normal':
                output += f"📊 Rolled with {result['advantage_type']}\n"
            
            return output
        else:
            return f"❌ Failed to roll dice: {response.get('error', 'Unknown error')}"
    
    def _handle_combat_command(self, instruction: str) -> str:
        """Handle combat-related commands"""
        instruction_lower = instruction.lower()
        
        # Start combat
        if "start combat" in instruction_lower or "begin combat" in instruction_lower:
            response = self._send_message_and_wait("combat_engine", "start_combat", {})
            if response and response.get("success"):
                output = "⚔️ **COMBAT STARTED!**\n\n"
                output += "📊 **Initiative Order:**\n"
                for name, init in response.get("initiative_order", []):
                    output += f"  • {name}: {init}\n"
                
                current = response.get("current_combatant")
                if current:
                    output += f"\n🎯 **Current Turn:** {current['name']}\n"
                
                return output
            else:
                return f"❌ Failed to start combat: {response.get('error', 'No combatants added')}"
        
        # Add combatant
        elif "add combatant" in instruction_lower or "add to combat" in instruction_lower:
            # Extract name and stats (simplified)
            words = instruction.split()
            name = "Unknown"
            hp = 10
            ac = 10
            
            for i, word in enumerate(words):
                if word.lower() in ["add", "combatant"] and i + 1 < len(words):
                    name = words[i + 1]
                    break
            
            response = self._send_message_and_wait("combat_engine", "add_combatant", {
                "name": name,
                "max_hp": hp,
                "armor_class": ac
            })
            
            if response and response.get("success"):
                return f"✅ Added {name} to combat"
            else:
                return f"❌ Failed to add combatant: {response.get('error', 'Unknown error')}"
        
        # Get combat status
        elif "combat status" in instruction_lower or "initiative order" in instruction_lower:
            response = self._send_message_and_wait("combat_engine", "get_combat_status", {})
            if response and response.get("success"):
                status = response["status"]
                output = f"⚔️ **Combat Status** (Round {status['round']})\n\n"
                
                for combatant in status["combatants"]:
                    marker = "👉 " if combatant["is_current"] else "   "
                    alive = "💀" if not combatant["is_alive"] else ""
                    output += f"{marker}{combatant['name']} - HP: {combatant['hp']}, AC: {combatant['ac']} {alive}\n"
                    if combatant["conditions"]:
                        output += f"    Conditions: {', '.join(combatant['conditions'])}\n"
                
                return output
            else:
                return f"❌ Failed to get combat status: {response.get('error', 'Unknown error')}"
        
        # Next turn
        elif "next turn" in instruction_lower or "end turn" in instruction_lower:
            response = self._send_message_and_wait("combat_engine", "next_turn", {})
            if response and response.get("success"):
                output = f"🔄 {response.get('message', 'Turn advanced')}\n"
                current = response.get("current_combatant")
                if current:
                    output += f"🎯 **Now active:** {current['name']} ({current['hp']} HP)"
                return output
            else:
                return f"❌ Failed to advance turn: {response.get('error', 'Unknown error')}"
        
        # End combat
        elif "end combat" in instruction_lower or "stop combat" in instruction_lower:
            response = self._send_message_and_wait("combat_engine", "end_combat", {})
            if response and response.get("success"):
                output = "🏁 **COMBAT ENDED!**\n\n"
                output += f"📊 Duration: {response['rounds']} rounds\n"
                output += f"⚡ Actions taken: {response['actions_taken']}\n"
                
                if response.get("survivors"):
                    output += "\n💚 **Survivors:**\n"
                    for survivor in response["survivors"]:
                        output += f"  • {survivor['name']} ({survivor['hp']} HP)\n"
                
                if response.get("casualties"):
                    output += "\n💀 **Casualties:**\n"
                    for casualty in response["casualties"]:
                        output += f"  • {casualty}\n"
                
                return output
            else:
                return f"❌ Failed to end combat: {response.get('error', 'Unknown error')}"
        
        else:
            return "❓ **Combat Commands:**\n• start combat\n• add combatant [name]\n• combat status\n• next turn\n• end combat"
    
    def _handle_rule_query(self, instruction: str) -> str:
        """Handle rule checking and clarification requests"""
        # Clean up the instruction to focus on the rule query
        query = instruction.lower()
        
        # Remove common command prefixes
        for prefix in ["check rule", "rule", "rules", "how does", "what happens when", "explain"]:
            if query.startswith(prefix):
                query = query[len(prefix):].strip()
                break
        
        # Determine rule category
        category = "general"
        if any(word in query for word in ["combat", "attack", "damage", "initiative", "opportunity"]):
            category = "combat"
        elif any(word in query for word in ["spell", "cast", "magic", "concentration"]):
            category = "spellcasting"
        elif any(word in query for word in ["move", "speed", "dash", "difficult terrain"]):
            category = "movement"
        elif any(word in query for word in ["save", "saving throw", "constitution save"]):
            category = "saving_throws"
        elif any(word in query for word in ["check", "skill", "ability score"]):
            category = "ability_checks"
        elif any(word in query for word in ["condition", "poisoned", "charmed", "stunned", "prone"]):
            category = "conditions"
        
        # Check if this is a condition query
        conditions = ["blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
                     "invisible", "paralyzed", "poisoned", "prone", "restrained", "stunned", "unconscious"]
        
        condition_found = None
        for condition in conditions:
            if condition in query:
                condition_found = condition
                break
        
        if condition_found:
            response = self._send_message_and_wait("rule_enforcement", "get_condition_effects", {
                "condition_name": condition_found
            }, timeout=15.0)
            
            if response and response.get("success"):
                effects = response["effects"]
                output = f"📖 **{condition_found.upper()} CONDITION**\n\n"
                output += "**Effects:**\n"
                for effect in effects.get("effects", []):
                    output += f"• {effect}\n"
                output += f"\n**Duration:** {effects.get('duration', 'Unknown')}\n"
                return output
        
        # General rule query
        response = self._send_message_and_wait("rule_enforcement", "check_rule", {
            "query": query,
            "category": category
        }, timeout=15.0)
        
        if response and response.get("success"):
            rule_info = response["rule_info"]
            output = f"📖 **{category.upper()} RULE**\n\n"
            output += f"**Rule:** {rule_info['rule_text']}\n\n"
            
            if rule_info.get("sources"):
                sources = rule_info['sources']
                if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                    # Handle dictionary sources
                    source_names = [source.get('source', str(source)) for source in sources]
                else:
                    # Handle string sources
                    source_names = sources if isinstance(sources, list) else [str(sources)]
                output += f"**Sources:** {', '.join(source_names)}\n"
            
            confidence = rule_info.get("confidence", "medium")
            confidence_emoji = {"high": "🔍", "medium": "📚", "low": "❓"}
            output += f"**Confidence:** {confidence_emoji.get(confidence, '📚')} {confidence}\n"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to find rule: {error_msg}"
    
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
                    
                    if dm_input.lower() == "help":
                        print("🎮 COMMANDS:")
                        print("  📚 Campaign: list campaigns, select campaign [n], campaign info")
                        print("  👥 Players: list players, player info [name]")
                        print("  🎭 Scenario: introduce scenario, generate [description], select option [n]")
                        print("  🎲 Dice: roll [dice expression], roll 1d20, roll 3d6+2")
                        print("  ⚔️  Combat: start combat, add combatant [name], combat status, next turn, end combat")
                        print("  📖 Rules: check rule [query], rule [topic], how does [mechanic] work")
                        print("  🖥️  System: agent status, game state")
                        print("  💬 General: Ask any D&D question for RAG-powered answers")
                        continue
                    
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
        
        assistant = ModularDMAssistant(
            collection_name=collection_name,
            verbose=True
        )
        
        assistant.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")


if __name__ == "__main__":
    main()