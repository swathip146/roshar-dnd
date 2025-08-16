"""
Modular RAG-Powered Dungeon Master Assistant
Orchestrates multiple AI agents using the agent framework for enhanced D&D gameplay
Enhanced with intelligent caching, async processing, and smart pipeline routing
"""
import json
import time
import asyncio
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from agent_framework import AgentOrchestrator, MessageType
from game_engine import GameEngineAgent, JSONPersister
from npc_controller import NPCControllerAgent
from scenario_generator import ScenarioGeneratorAgent
from campaign_management import CampaignManagerAgent
from haystack_pipeline_agent import HaystackPipelineAgent
# Removed redundant RAG imports - using HaystackPipelineAgent only
from dice_system import DiceSystemAgent, DiceRoller
from combat_engine import CombatEngineAgent, CombatEngine
from rule_enforcement_agent import RuleEnforcementAgent

# New D&D-specific agents
from character_manager_agent import CharacterManagerAgent
from session_manager_agent import SessionManagerAgent
from inventory_manager_agent import InventoryManagerAgent
from spell_manager_agent import SpellManagerAgent
from experience_manager_agent import ExperienceManagerAgent

# Removed over-engineered pipeline components - using simple inline methods instead

# Claude-specific imports for text processing
CLAUDE_AVAILABLE = True

# Simple command mapping dictionary - replaces complex CommandMapper class
COMMAND_MAP = {
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

def get_command_help() -> str:
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


class NarrativeContinuityTracker:
    """Enhanced story consistency tracking for Priority 3 improvements"""
    
    def __init__(self):
        self.story_elements = {
            'characters': {},
            'locations': {},
            'plot_threads': {},
            'unresolved_conflicts': []
        }
        self.consistency_score = 1.0
        self.narrative_history = []
    
    def analyze_narrative_consistency(self, new_content: str, context: dict) -> dict:
        """Analyze new content for consistency with established narrative"""
        # Extract entities and themes
        entities = self._extract_entities(new_content)
        themes = self._extract_themes(new_content)
        
        # Check for contradictions
        contradictions = self._check_contradictions(entities, themes)
        
        # Update story elements
        self._update_story_elements(entities, themes)
        
        # Calculate coherence score
        coherence_score = self._calculate_coherence_score()
        
        # Store in history
        self.narrative_history.append({
            'content': new_content,
            'entities': entities,
            'themes': themes,
            'contradictions': contradictions,
            'coherence_score': coherence_score,
            'timestamp': __import__('time').time()
        })
        
        return {
            'consistency_score': self.consistency_score,
            'contradictions': contradictions,
            'narrative_coherence': coherence_score,
            'entities_found': entities,
            'themes_identified': themes
        }
    
    def _extract_entities(self, content: str) -> dict:
        """Extract character and location entities from content"""
        import re
        
        entities = {'characters': [], 'locations': [], 'items': []}
        
        # Simple entity extraction patterns
        character_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:says|does|moves|attacks|casts)',
            r'(?:NPC|character|person|being)\s+named\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        location_patterns = [
            r'(?:in|at|near|to|from)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Temple|Castle|Inn|Tavern|Forest|Mountain|Cave|Tower)))',
            r'(?:location|place|area|region)\s+(?:called|named)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in character_patterns:
            matches = re.findall(pattern, content)
            entities['characters'].extend(matches)
        
        for pattern in location_patterns:
            matches = re.findall(pattern, content)
            entities['locations'].extend(matches)
        
        return entities
    
    def _extract_themes(self, content: str) -> list:
        """Extract narrative themes from content"""
        themes = []
        content_lower = content.lower()
        
        theme_keywords = {
            'conflict': ['battle', 'fight', 'war', 'conflict', 'struggle'],
            'mystery': ['mystery', 'unknown', 'secret', 'hidden', 'investigate'],
            'exploration': ['explore', 'discover', 'journey', 'travel', 'adventure'],
            'magic': ['magic', 'spell', 'enchanted', 'mystical', 'arcane'],
            'social': ['negotiate', 'persuade', 'diplomacy', 'politics', 'alliance']
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                themes.append(theme)
        
        return themes
    
    def _check_contradictions(self, entities: dict, themes: list) -> list:
        """Check for narrative contradictions"""
        contradictions = []
        
        # Check character consistency
        for char in entities.get('characters', []):
            if char in self.story_elements['characters']:
                stored_char = self.story_elements['characters'][char]
                # Simple contradiction check - character appearing in impossible situations
                if stored_char.get('status') == 'dead' and char in entities['characters']:
                    contradictions.append(f"Character {char} appears despite being marked as dead")
        
        return contradictions
    
    def _update_story_elements(self, entities: dict, themes: list):
        """Update tracked story elements"""
        # Update characters
        for char in entities.get('characters', []):
            if char not in self.story_elements['characters']:
                self.story_elements['characters'][char] = {
                    'first_appearance': __import__('time').time(),
                    'status': 'alive',
                    'appearances': 1
                }
            else:
                self.story_elements['characters'][char]['appearances'] += 1
        
        # Update locations
        for loc in entities.get('locations', []):
            if loc not in self.story_elements['locations']:
                self.story_elements['locations'][loc] = {
                    'first_mention': __import__('time').time(),
                    'visits': 1
                }
            else:
                self.story_elements['locations'][loc]['visits'] += 1
    
    def _calculate_coherence_score(self) -> float:
        """Calculate narrative coherence score"""
        if len(self.narrative_history) < 2:
            return 1.0
        
        # Simple coherence calculation based on entity consistency
        total_elements = 0
        consistent_elements = 0
        
        for char_data in self.story_elements['characters'].values():
            total_elements += 1
            if char_data['appearances'] > 1:  # Character has continuity
                consistent_elements += 1
        
        for loc_data in self.story_elements['locations'].values():
            total_elements += 1
            if loc_data['visits'] > 1:  # Location has continuity
                consistent_elements += 1
        
        return consistent_elements / max(total_elements, 1)


# Removed AdaptiveErrorRecovery and PerformanceMonitoringDashboard classes
# These were over-engineered components that added unnecessary complexity


class SimpleInlineCache:
    """Simple TTL-based in-memory cache for basic caching needs"""
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
    
    def get(self, key: str, default_ttl_hours: float = 1.0):
        """Get value from cache if not expired"""
        if key not in self.cache:
            return None
        
        # Check if expired
        import time
        current_time = time.time()
        if key in self.timestamps:
            cache_time, ttl_seconds = self.timestamps[key]
            if current_time - cache_time > ttl_seconds:
                # Expired, remove from cache
                del self.cache[key]
                del self.timestamps[key]
                return None
        
        return self.cache[key]
    
    def set(self, key: str, value, ttl_hours: float = 1.0):
        """Set value in cache with TTL"""
        import time
        self.cache[key] = value
        self.timestamps[key] = (time.time(), ttl_hours * 3600)  # Convert hours to seconds
    
    def delete(self, key: str):
        """Delete specific key from cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
    
    def clear(self):
        """Clear all cached items"""
        self.cache.clear()
        self.timestamps.clear()
    
    def cleanup_expired(self):
        """Remove all expired items from cache"""
        import time
        current_time = time.time()
        expired_keys = []
        
        for key, (cache_time, ttl_seconds) in self.timestamps.items():
            if current_time - cache_time > ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self.cache:
                del self.cache[key]
            del self.timestamps[key]
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        # Clean up expired items first
        self.cleanup_expired()
        
        return {
            'total_items': len(self.cache),
            'memory_usage_estimate': sum(len(str(k)) + len(str(v)) for k, v in self.cache.items()),
            'oldest_item_age_seconds': self._get_oldest_item_age()
        }
    
    def _get_oldest_item_age(self) -> float:
        """Get age of oldest cached item in seconds"""
        if not self.timestamps:
            return 0.0
        
        import time
        current_time = time.time()
        oldest_time = min(cache_time for cache_time, _ in self.timestamps.values())
        return current_time - oldest_time


class ModularDMAssistant:
    """
    Enhanced Modular DM Assistant with intelligent caching, async processing, and smart routing
    Orchestrates multiple AI agents using the agent framework for comprehensive D&D management
    """
    
    def __init__(self,
                 collection_name: str = "dnd_documents",
                 campaigns_dir: str = "docs/current_campaign",
                 players_dir: str = "docs/players",
                 verbose: bool = False,
                 enable_game_engine: bool = True,
                 tick_seconds: float = 0.8,
                 enable_caching: bool = True,
                 enable_async: bool = True,
                 game_save_file: Optional[str] = None):
        """Initialize the enhanced modular DM assistant"""
        
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
        
        # Simple caching only - removed complex pipeline management
        self.inline_cache = SimpleInlineCache() if enable_caching else None
        
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
        
        # New D&D-specific agents
        self.character_agent: Optional[CharacterManagerAgent] = None
        self.session_agent: Optional[SessionManagerAgent] = None
        self.inventory_agent: Optional[InventoryManagerAgent] = None
        self.spell_agent: Optional[SpellManagerAgent] = None
        self.experience_agent: Optional[ExperienceManagerAgent] = None
        
        # RAG functionality now handled by HaystackPipelineAgent only
        
        # Game state tracking
        self.game_state = {}
        self.last_command = ""
        self.last_scenario_options = []  # Store last generated options for choice selection
        
        # Enhanced story consistency tracking (Priority 3)
        self.narrative_tracker = NarrativeContinuityTracker() if enable_caching else None
        
        # Removed over-engineered components: AdaptiveErrorRecovery and PerformanceMonitoringDashboard
        
        # Simple command mapping - no complex class needed
        self.command_map = COMMAND_MAP
        
        # Initialize all components
        self._initialize_agents()
        
        # Load game save if specified
        if self.current_save_file:
            self._load_game_save(self.current_save_file)
        
        if self.verbose:
            print("🚀 Enhanced Modular DM Assistant initialized with intelligent pipelines")
            if self.current_save_file:
                print(f"💾 Loaded game save: {self.current_save_file}")
            # Note: Agent status will be printed after orchestrator starts
            self._print_pipeline_status()
    
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
            
            # 6. RAG agent removed - using HaystackPipelineAgent only
            
            # 7. Initialize Rule Enforcement Agent
            self.rule_agent = RuleEnforcementAgent(
                rag_agent=self.haystack_agent,  # Use HaystackPipelineAgent instead
                strict_mode=False
            )
            self.orchestrator.register_agent(self.rule_agent)
            
            # 8. Initialize NPC Controller Agent
            self.npc_agent = NPCControllerAgent(
                haystack_agent=self.haystack_agent,  # Use HaystackPipelineAgent instead
                mode="hybrid"
            )
            self.orchestrator.register_agent(self.npc_agent)
            
            # 9. Initialize Scenario Generator Agent
            self.scenario_agent = ScenarioGeneratorAgent(
                haystack_agent=self.haystack_agent,
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.scenario_agent)
            
            # 10. Initialize Character Manager Agent
            self.character_agent = CharacterManagerAgent(
                characters_dir="docs/characters",
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.character_agent)
            
            # 11. Initialize Session Manager Agent
            self.session_agent = SessionManagerAgent(
                sessions_dir="docs/sessions",
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.session_agent)
            
            # 12. Initialize Inventory Manager Agent
            self.inventory_agent = InventoryManagerAgent(
                inventory_dir="docs/inventory",
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.inventory_agent)
            
            # 13. Initialize Spell Manager Agent
            self.spell_agent = SpellManagerAgent(
                spells_dir="docs/spells",
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.spell_agent)
            
            # 14. Initialize Experience Manager Agent
            self.experience_agent = ExperienceManagerAgent(
                xp_dir="docs/experience",
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.experience_agent)
            
            if self.verbose:
                print("✅ All agents initialized successfully (including new D&D agents)")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize agents: {e}")
            raise
    
    # Removed _setup_enhanced_pipelines method - no longer needed with simplified architecture
    
    def _print_pipeline_status(self):
        """Print status of simplified system components"""
        print("\n🔧 SYSTEM STATUS:")
        print(f"  • Simple Caching: {'✅ Enabled' if self.enable_caching else '❌ Disabled'}")
        print(f"  • Async Processing: {'✅ Enabled' if self.enable_async else '❌ Disabled'}")
        
        # Show cache statistics
        if self.enable_caching and self.inline_cache:
            inline_stats = self.inline_cache.get_stats()
            print(f"  • Inline Cache: {inline_stats['total_items']} items cached")
        print()
    
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
                
                # Brief pause to allow agents to fully initialize
                import time
                time.sleep(0.2)
                
                # Now print agent status after they've started
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
    
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction using simplified command mapping"""
        instruction_lower = instruction.lower().strip()
        
        # Handle help command directly
        if instruction_lower == "help":
            return get_command_help()
        
        # Handle system commands directly
        if instruction_lower in ["agent status", "system status"]:
            return self._get_system_status()
        
        # Handle numeric input for campaign selection
        if instruction_lower.isdigit() and self.last_command == "list_campaigns":
            campaign_idx = int(instruction_lower) - 1
            response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
            self.last_command = ""
            if response and response.get("success"):
                return f"✅ Selected campaign: {response['campaign']}"
            else:
                return f"❌ {response.get('error', 'Failed to select campaign')}"
        
        # Check for direct command matches
        for pattern, (agent, action) in self.command_map.items():
            if pattern in instruction_lower:
                return self._route_command(agent, action, instruction)
        
        # Handle special patterns with parameters
        if instruction_lower.startswith('roll '):
            return self._handle_dice_roll(instruction)
        elif instruction_lower.startswith('rule ') or 'how does' in instruction_lower or self._is_condition_query(instruction_lower):
            return self._handle_rule_query(instruction)
        elif self._is_scenario_request(instruction_lower):
            return self._generate_scenario(instruction)
        elif instruction_lower.startswith('select option'):
            import re
            match = re.search(r'select option (\d+)', instruction_lower)
            if match:
                return self._select_player_option(int(match.group(1)))
        
        # Fallback to general query
        return self._handle_general_query(instruction)
    
    def _route_command(self, agent_id: str, action: str, instruction: str) -> str:
        """Route command to appropriate agent"""
        if agent_id == 'campaign_manager':
            if action == 'list_campaigns':
                return self._handle_list_campaigns(instruction, {})
            elif action == 'get_campaign_info':
                return self._handle_campaign_info(instruction, {})
            elif action == 'list_players':
                return self._handle_list_players(instruction, {})
        elif agent_id == 'combat_engine':
            return self._handle_combat_command(instruction)
        elif agent_id == 'dice_system':
            return self._handle_dice_roll(instruction)
        elif agent_id == 'rule_enforcement':
            return self._handle_rule_query(instruction)
        elif agent_id == 'game_engine':
            if action == 'save_game':
                return self._handle_save_game(instruction, self._extract_params(instruction))
            elif action == 'load_game':
                return self._handle_load_game(instruction, {})
            elif action == 'list_saves':
                return self._handle_list_saves(instruction, {})
            elif action == 'load_save':
                return self._handle_load_save(instruction, self._extract_params(instruction))
            elif action == 'get_game_state':
                return self._handle_game_state(instruction, {})
            else:
                return self._handle_general_query(instruction)
        elif agent_id == 'haystack_pipeline':
            if action == 'query_scenario':
                return self._generate_scenario(instruction)
            else:
                return self._handle_general_query(instruction)
        elif agent_id == 'scenario_generator':
            if action == 'apply_player_choice':
                # Extract option number from instruction
                import re
                match = re.search(r'select option (\d+)', instruction.lower())
                if match:
                    option_number = int(match.group(1))
                    return self._select_player_option(option_number)
                else:
                    return "❌ Please specify option number (e.g., 'select option 2')"
            else:
                return self._handle_general_query(instruction)
        elif agent_id == 'session_manager':
            if 'short rest' in instruction:
                return self._handle_short_rest(instruction, {})
            elif 'long rest' in instruction or 'sleep' in instruction:
                return self._handle_long_rest(instruction, {})
        elif agent_id == 'orchestrator':
            return self._handle_system_status(instruction, {})
        
        # Default fallback
        return self._handle_general_query(instruction)
    
    # Command Handler Methods
    def _handle_list_campaigns(self, instruction: str, params: dict) -> str:
        """Handle list campaigns command"""
        response = self._send_message_and_wait("campaign_manager", "list_campaigns", {})
        if response:
            campaigns = response.get("campaigns", [])
            if campaigns:
                self.last_command = "list_campaigns"
                return "📚 AVAILABLE CAMPAIGNS:\n" + "\n".join(campaigns) + "\n\n💡 *Type the campaign number to select it*"
            else:
                return "❌ No campaigns available. Check campaigns directory."
        return "❌ Failed to retrieve campaigns"
    
    def _handle_select_campaign(self, instruction: str, params: dict) -> str:
        """Handle select campaign command"""
        # Extract campaign number from params
        campaign_idx = None
        if 'param_1' in params and params['param_1'].isdigit():
            campaign_idx = int(params['param_1']) - 1
        
        if campaign_idx is not None:
            response = self._send_message_and_wait("campaign_manager", "select_campaign", {"index": campaign_idx})
            if response and response.get("success"):
                return f"✅ Selected campaign: {response['campaign']}"
            else:
                return f"❌ {response.get('error', 'Failed to select campaign')}"
        else:
            # Show available campaigns
            response = self._send_message_and_wait("campaign_manager", "list_campaigns", {})
            if response:
                campaigns = response.get("campaigns", [])
                return f"❌ Please specify campaign number (1-{len(campaigns)})"
            return "❌ No campaigns available"
    
    def _handle_campaign_info(self, instruction: str, params: dict) -> str:
        """Handle campaign info command"""
        response = self._send_message_and_wait("campaign_manager", "get_campaign_info", {})
        if response and response.get("success"):
            return self._format_campaign_info(response["campaign"])
        else:
            return f"❌ {response.get('error', 'No campaign selected')}"
    
    def _handle_list_players(self, instruction: str, params: dict) -> str:
        """Handle list players command"""
        response = self._send_message_and_wait("campaign_manager", "list_players", {})
        if response:
            return self._format_player_list(response.get("players", []))
        return "❌ Failed to retrieve players"
    
    def _handle_player_info(self, instruction: str, params: dict) -> str:
        """Handle player info command"""
        player_name = params.get('param_1', '').strip()
        
        if player_name:
            response = self._send_message_and_wait("campaign_manager", "get_player_info", {"name": player_name})
            if response and response.get("success"):
                return self._format_player_info(response["player"])
            else:
                return f"❌ {response.get('error', 'Player not found')}"
        else:
            return "❌ Please specify player name. Usage: player info [name]"
    
    def _handle_roll_dice(self, instruction: str, params: dict) -> str:
        """Handle dice rolling command"""
        return self._handle_dice_roll(instruction)
    
    def _handle_start_combat(self, instruction: str, params: dict) -> str:
        """Handle start combat command"""
        return self._handle_combat_command(instruction)
    
    def _handle_combat_status(self, instruction: str, params: dict) -> str:
        """Handle combat status command"""
        return self._handle_combat_command(instruction)
    
    def _handle_next_turn(self, instruction: str, params: dict) -> str:
        """Handle next turn command"""
        return self._handle_combat_command(instruction)
    
    def _handle_end_combat(self, instruction: str, params: dict) -> str:
        """Handle end combat command"""
        return self._handle_combat_command(instruction)
    
    def _handle_check_rule(self, instruction: str, params: dict) -> str:
        """Handle rule checking command"""
        return self._handle_rule_query(instruction)
    
    def _handle_generate_scenario(self, instruction: str, params: dict) -> str:
        """Handle scenario generation command"""
        return self._generate_scenario(instruction)
    
    def _handle_select_option(self, instruction: str, params: dict) -> str:
        """Handle option selection command"""
        option_num = None
        if 'param_1' in params and params['param_1'].isdigit():
            option_num = int(params['param_1'])
        
        if option_num:
            return self._select_player_option(option_num)
        else:
            return "❌ Please specify option number (e.g., 'select option 2')"
    
    def _handle_save_game(self, instruction: str, params: dict) -> str:
        """Handle save game command"""
        save_name = params.get('param_1', 'Quick Save').strip()
        if not save_name:
            save_name = "Quick Save"
        
        if self._save_game(save_name):
            return f"💾 Game saved successfully as: {save_name}"
        else:
            return "❌ Failed to save game"
    
    def _handle_load_game(self, instruction: str, params: dict) -> str:
        """Handle load game command - just shows help"""
        return "💡 Use 'list saves' to see available saves, or 'load save [number]' to load a specific save"
    
    def _handle_list_saves(self, instruction: str, params: dict) -> str:
        """Handle list saves command"""
        saves = self._list_game_saves()
        if not saves:
            return "❌ No game saves found in ./game_saves directory"
        
        output = "💾 AVAILABLE GAME SAVES:\n\n"
        for i, save in enumerate(saves, 1):
            output += f"  {i}. **{save['save_name']}**\n"
            output += f"     Campaign: {save['campaign']}\n"
            output += f"     Last Modified: {save['last_modified']}\n"
            output += f"     Progress: {save['scenario_count']} scenarios, {save['story_progression']} story events\n"
            output += f"     Players: {save['players']}\n\n"
        
        output += "💡 *Type 'load save [number]' to load a specific save*"
        return output
    
    def _handle_load_save(self, instruction: str, params: dict) -> str:
        """Handle load save command"""
        save_number = None
        if 'param_1' in params and params['param_1'].isdigit():
            save_number = int(params['param_1'])
        
        if save_number is None:
            return "❌ Please specify save number (e.g., 'load save 1')"
        
        saves = self._list_game_saves()
        if save_number < 1 or save_number > len(saves):
            return f"❌ Invalid save number. Available saves: 1-{len(saves)}"
        
        selected_save = saves[save_number - 1]
        if self._load_game_save(selected_save['filename']):
            return f"✅ Successfully loaded: {selected_save['save_name']}"
        else:
            return f"❌ Failed to load save: {selected_save['save_name']}"
    
    def _handle_game_state(self, instruction: str, params: dict) -> str:
        """Handle game state command"""
        if self.game_engine_agent:
            response = self._send_message_and_wait("game_engine", "get_game_state", {})
            if response and response.get("game_state"):
                return f"📊 GAME STATE:\n{json.dumps(response['game_state'], indent=2)}"
        return "❌ Game state not available"
    
    def _handle_system_status(self, instruction: str, params: dict) -> str:
        """Handle system status command"""
        return self._get_system_status()
    
    def _handle_create_character(self, instruction: str, params: dict) -> str:
        """Handle create character command"""
        character_name = params.get('param_1', '').strip()
        if not character_name:
            return "❌ Please specify character name. Usage: create character [name]"
        
        # Basic character creation - could be enhanced with prompts for race, class, etc.
        response = self._send_message_and_wait("character_manager", "create_character", {
            "name": character_name,
            "race": "Human",  # Default values - could be made interactive
            "character_class": "Fighter",
            "level": 1
        })
        
        if response and response.get("success"):
            return f"🎭 **CHARACTER CREATED!**\n{response['message']}\n\n📊 **Stats:**\n{response.get('character_summary', 'Character created successfully')}"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to create character: {error_msg}"
    
    def _handle_level_up(self, instruction: str, params: dict) -> str:
        """Handle level up command"""
        character_name = params.get('param_1', '').strip()
        if not character_name:
            return "❌ Please specify character name. Usage: level up [name]"
        
        # Level up character using experience manager
        response = self._send_message_and_wait("experience_manager", "level_up", {
            "character": character_name
        })
        
        if response and response.get("success"):
            return f"⬆️ **LEVEL UP!**\n{response['message']}\n\n🎉 **Level Benefits:**\n{self._format_level_benefits(response.get('level_benefits', {}))}"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to level up: {error_msg}"
    
    def _handle_short_rest(self, instruction: str, params: dict) -> str:
        """Handle short rest command"""
        response = self._send_message_and_wait("session_manager", "take_short_rest", {})
        
        if response and response.get("success"):
            benefits = response.get("benefits", {})
            output = f"😴 **SHORT REST COMPLETED!**\n{response['message']}\n\n"
            
            if benefits.get("hit_dice_recovered"):
                output += f"💚 Hit Dice Available: {benefits['hit_dice_recovered']}\n"
            if benefits.get("abilities_recharged"):
                output += f"⚡ Abilities Recharged: {', '.join(benefits['abilities_recharged'])}\n"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to take short rest: {error_msg}"
    
    def _handle_long_rest(self, instruction: str, params: dict) -> str:
        """Handle long rest command"""
        response = self._send_message_and_wait("session_manager", "take_long_rest", {})
        
        if response and response.get("success"):
            benefits = response.get("benefits", {})
            output = f"🛌 **LONG REST COMPLETED!**\n{response['message']}\n\n"
            
            if benefits.get("hp_restored"):
                output += f"💚 HP Fully Restored\n"
            if benefits.get("spell_slots_restored"):
                output += f"✨ All Spell Slots Restored\n"
            if benefits.get("abilities_recharged"):
                output += f"⚡ All Abilities Recharged\n"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to take long rest: {error_msg}"
    
    def _handle_add_item(self, instruction: str, params: dict) -> str:
        """Handle add item command"""
        item_name = params.get('param_1', '').strip()
        if not item_name:
            return "❌ Please specify item name. Usage: add item [name]"
        
        # Extract character name if provided, otherwise use default
        character_name = params.get('param_2', 'party').strip()
        
        response = self._send_message_and_wait("inventory_manager", "add_item", {
            "character": character_name,
            "item_name": item_name,
            "quantity": 1
        })
        
        if response and response.get("success"):
            return f"🎒 **ITEM ADDED!**\n{response['message']}"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to add item: {error_msg}"
    
    def _handle_remove_item(self, instruction: str, params: dict) -> str:
        """Handle remove item command"""
        item_name = params.get('param_1', '').strip()
        if not item_name:
            return "❌ Please specify item name. Usage: remove item [name]"
        
        character_name = params.get('param_2', 'party').strip()
        
        response = self._send_message_and_wait("inventory_manager", "remove_item", {
            "character": character_name,
            "item_name": item_name,
            "quantity": 1
        })
        
        if response and response.get("success"):
            return f"🗑️ **ITEM REMOVED!**\n{response['message']}"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to remove item: {error_msg}"
    
    def _handle_show_inventory(self, instruction: str, params: dict) -> str:
        """Handle show inventory command"""
        character_name = params.get('param_1', 'party').strip()
        
        response = self._send_message_and_wait("inventory_manager", "get_inventory", {
            "character": character_name
        })
        
        if response and response.get("success"):
            inventory = response.get("inventory", {})
            output = f"🎒 **INVENTORY ({character_name})**\n\n"
            
            items = inventory.get("items", [])
            if items:
                for item in items:
                    output += f"• {item['name']} (x{item['quantity']})"
                    if item.get('weight'):
                        output += f" - {item['weight']} lbs"
                    output += "\n"
                
                carry_info = inventory.get("carrying_capacity", {})
                if carry_info:
                    output += f"\n📊 **Carrying Capacity:** {carry_info.get('current_weight', 0)}/{carry_info.get('max_capacity', 'Unknown')} lbs"
            else:
                output += "No items in inventory."
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to show inventory: {error_msg}"
    
    def _handle_cast_spell(self, instruction: str, params: dict) -> str:
        """Handle cast spell command"""
        spell_name = params.get('param_1', '').strip()
        if not spell_name:
            return "❌ Please specify spell name. Usage: cast [spell name]"
        
        character_name = params.get('param_2', 'caster').strip()
        
        response = self._send_message_and_wait("spell_manager", "cast_spell", {
            "character": character_name,
            "spell": spell_name
        })
        
        if response and response.get("success"):
            output = f"✨ **SPELL CAST!**\n{response['message']}\n\n"
            
            spell_info = response.get("spell", {})
            if spell_info:
                output += f"📖 **{spell_info.get('name', spell_name)}**\n"
                output += f"Level: {spell_info.get('level', 'Unknown')}\n"
                output += f"Range: {spell_info.get('range', 'Unknown')}\n"
                output += f"Duration: {spell_info.get('duration', 'Unknown')}\n"
            
            if response.get("spell_slot_used"):
                output += f"\n🔮 Used Level {response['spell_slot_used']} Spell Slot"
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to cast spell: {error_msg}"
    
    def _handle_prepare_spells(self, instruction: str, params: dict) -> str:
        """Handle prepare spells command"""
        character_name = params.get('param_1', 'caster').strip()
        
        response = self._send_message_and_wait("spell_manager", "get_prepared_spells", {
            "character": character_name
        })
        
        if response and response.get("success"):
            prepared = response.get("prepared_spells", [])
            cantrips = response.get("cantrips", [])
            
            output = f"📚 **PREPARED SPELLS ({character_name})**\n\n"
            
            if cantrips:
                output += "**Cantrips:**\n"
                for cantrip in cantrips:
                    output += f"• {cantrip}\n"
                output += "\n"
            
            if prepared:
                output += "**Prepared Spells:**\n"
                for spell in prepared:
                    output += f"• {spell}\n"
            else:
                output += "No spells currently prepared."
            
            return output
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to show prepared spells: {error_msg}"
    
    def _format_level_benefits(self, level_benefits: dict) -> str:
        """Format level benefits for display"""
        if not level_benefits:
            return "Level benefits information not available"
        
        output = ""
        level = level_benefits.get("level", "Unknown")
        prof_bonus = level_benefits.get("proficiency_bonus", "Unknown")
        asi = level_benefits.get("ability_score_improvement", False)
        general_benefits = level_benefits.get("general_benefits", [])
        
        output += f"**Level:** {level}\n"
        output += f"**Proficiency Bonus:** +{prof_bonus}\n"
        
        if asi:
            output += "🎯 **Ability Score Improvement Available!**\n"
        
        if general_benefits:
            output += "**General Benefits:**\n"
            for benefit in general_benefits:
                output += f"• {benefit}\n"
        
        return output

    def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Send a message to an agent and wait for response with simple caching and timeout handling"""
        try:
            # Check if agent is registered and has handlers before attempting communication
            if not self._check_agent_availability(agent_id, action):
                if self.verbose:
                    print(f"⚠️ Agent {agent_id} not available or missing handler for {action}")
                return {"success": False, "error": f"Agent {agent_id} not available"}

            # Simple caching for cacheable queries
            cache_key = None
            if self.enable_caching and self.inline_cache and self._should_cache_simple(agent_id, action, data):
                cache_key = f"{agent_id}_{action}_{json.dumps(data, sort_keys=True)}"
                cached_result = self.inline_cache.get(cache_key)
                if cached_result:
                    if self.verbose:
                        print(f"📦 Cache hit for {agent_id}:{action}")
                    return cached_result
            
            # Send message through orchestrator with retry mechanism
            message_id = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    message_id = self.orchestrator.send_message_to_agent(agent_id, action, data)
                    if message_id:
                        break
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Message send attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(0.2)  # Brief pause between retries
            
            if not message_id:
                if self.verbose:
                    print(f"❌ Failed to send message to {agent_id} after {max_retries} attempts")
                return {"success": False, "error": "Failed to send message"}
            
            # Wait for response in message history with improved polling
            start_time = time.time()
            result = None
            poll_interval = 0.1
            last_poll_time = 0
            
            while time.time() - start_time < timeout:
                current_time = time.time()
                
                # Adaptive polling - increase interval slightly over time to reduce CPU usage
                if current_time - last_poll_time >= poll_interval:
                    try:
                        history = self.orchestrator.message_bus.get_message_history(limit=50)
                        for msg in reversed(history):
                            if (msg.get("response_to") == message_id and
                                msg.get("message_type") == "response"):
                                result = msg.get("data", {})
                                break
                        
                        if result:
                            break
                        
                        last_poll_time = current_time
                        # Gradually increase poll interval to reduce CPU usage
                        poll_interval = min(0.3, poll_interval * 1.05)
                        
                    except Exception as e:
                        if self.verbose:
                            print(f"⚠️ Error checking message history: {e}")
                        
                time.sleep(0.05)  # Small sleep to prevent busy waiting
            
            # Simple caching of successful results
            if result and cache_key and self.inline_cache:
                # Set appropriate TTL based on query type
                ttl_hours = self._get_simple_cache_ttl(agent_id, action)
                self.inline_cache.set(cache_key, result, ttl_hours)
                
                if self.verbose:
                    print(f"💾 Cached result for {agent_id}:{action} (TTL: {ttl_hours}h)")
            
            # Enhanced timeout handling with detailed error reporting
            if not result:
                elapsed_time = time.time() - start_time
                if self.verbose:
                    print(f"⚠️ Timeout waiting for response from {agent_id}:{action} (waited {elapsed_time:.2f}s)")
                    print(f"📊 Agent status: {self._get_agent_quick_status(agent_id)}")
                
                # Return a structured timeout error instead of None
                return {
                    "success": False,
                    "error": f"Agent communication timeout after {elapsed_time:.2f}s",
                    "agent_id": agent_id,
                    "action": action,
                    "timeout_duration": elapsed_time
                }
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error sending message to {agent_id}:{action}: {e}")
                import traceback
                print(f"🔍 Stack trace: {traceback.format_exc()}")
            
            # Return a structured error instead of None
            return {
                "success": False,
                "error": f"Communication error: {str(e)}",
                "agent_id": agent_id,
                "action": action
            }
    
    def _should_cache_simple(self, agent_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Determine if a query should be cached using simple rules"""
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
        
        # Cache rule queries, campaign info, and other static content
        return True
    
    def _get_simple_cache_ttl(self, agent_id: str, action: str) -> float:
        """Get cache TTL (time-to-live) in hours for different agent/action combinations"""
        # Rule queries can be cached longer since they're static
        if agent_id == 'rule_enforcement':
            return 24.0
        
        # Campaign info can be cached for medium duration
        if agent_id == 'campaign_manager':
            return 12.0
        
        # General queries use shorter TTL
        return 6.0
    
    def _check_agent_availability(self, agent_id: str, action: str) -> bool:
        """Check if agent is registered and has the required handler"""
        try:
            # Check if agent is registered with orchestrator
            agent_status = self.orchestrator.get_agent_status()
            if agent_id not in agent_status:
                if self.verbose:
                    print(f"🔍 Agent {agent_id} not found in registered agents: {list(agent_status.keys())}")
                return False
            
            # Check if agent is running
            if not agent_status[agent_id].get("running", False):
                if self.verbose:
                    print(f"🔍 Agent {agent_id} is not running")
                return False
            
            # Check if agent has the required handler
            handlers = agent_status[agent_id].get("handlers", [])
            if action not in handlers:
                if self.verbose:
                    print(f"🔍 Agent {agent_id} missing handler '{action}'. Available: {handlers}")
                return False
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error checking agent availability: {e}")
            return False
    
    def _get_agent_quick_status(self, agent_id: str) -> str:
        """Get quick status information about an agent"""
        try:
            agent_status = self.orchestrator.get_agent_status()
            if agent_id not in agent_status:
                return "Not registered"
            
            info = agent_status[agent_id]
            running = "Running" if info.get("running", False) else "Stopped"
            handler_count = len(info.get("handlers", []))
            
            return f"{running}, {handler_count} handlers"
            
        except Exception as e:
            return f"Status check failed: {e}"
    
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
        """Generate scenario with enhanced performance optimization and parallel context gathering"""
        try:
            # Use async context gathering for better performance
            if self.enable_async:
                return self._generate_scenario_optimized_async(user_query)
            else:
                return self._generate_scenario_standard(user_query)
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Optimized scenario generation failed, falling back: {e}")
            return self._generate_scenario_standard(user_query)
    
    def _generate_scenario_optimized_async(self, user_query: str) -> str:
        """Optimized scenario generation with parallel processing and smart context reduction"""
        import asyncio
        
        async def gather_context_async():
            """Gather context data in parallel for faster processing"""
            tasks = []
            
            # Task 1: Get campaign context
            if self.campaign_agent:
                tasks.append(self._get_campaign_context_async())
            
            # Task 2: Get game state
            if self.game_engine_agent:
                tasks.append(self._get_game_state_async())
            
            # Execute tasks in parallel
            if tasks:
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    campaign_context = results[0] if len(results) > 0 and not isinstance(results[0], Exception) else {}
                    game_state = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else {}
                    return campaign_context, game_state
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Parallel context gathering failed: {e}")
                    return {}, {}
            
            return {}, {}
        
        # Run async context gathering
        try:
            campaign_context, game_state_dict = asyncio.run(gather_context_async())
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Async context gathering failed, using sequential: {e}")
            return self._generate_scenario_standard(user_query)
        
        # Smart context reduction - keep only essential information
        optimized_context = self._create_optimized_context(campaign_context, game_state_dict, user_query)
        
        # Build enhanced query with reduced context for faster processing
        enhanced_query = self._build_enhanced_query(user_query, optimized_context)
        
        # Generate scenario with optimized parameters (reduced timeout for faster response)
        response = self._send_message_and_wait("haystack_pipeline", "query_scenario", {
            "query": enhanced_query,
            "campaign_context": json.dumps(optimized_context.get("campaign", {})),
            "game_state": json.dumps(optimized_context.get("game_state", {}))
        }, timeout=20.0)  # Reduced from 30.0 to 20.0 for faster response
        
        if response and response.get("success"):
            result = response["result"]
            scenario_text = result.get("answer", "Failed to generate scenario")
            
            # Extract and store options for later use
            self._extract_and_store_options(scenario_text)
            
            # Update game state asynchronously to not block response
            if self.game_engine_agent and game_state_dict:
                self._update_game_state_async(user_query, scenario_text, game_state_dict)
            
            if self.verbose:
                print("🚀 Used optimized scenario generation with parallel context gathering")
            
            # Check if scenario generation actually failed due to no connection
            if "Pipeline not available" in scenario_text or "not connected" in scenario_text:
                # Provide fallback scenario with proper numbered options when RAG is not available
                fallback_scenario = """The party finds themselves at a crossroads where four paths diverge into the unknown.

**1. Take the North Path** - Follow the well-worn trail toward distant mountains
**2. Take the East Path** - Head through the dense forest where strange sounds echo
**3. Take the West Path** - Follow the river downstream toward civilization
**4. Make Camp Here** - Rest and prepare before choosing a direction"""
                
                # Extract and store the fallback options
                self._extract_and_store_options(fallback_scenario)
                return f"🎭 SCENARIO (Fallback - RAG Offline):\n{fallback_scenario}\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
            else:
                return f"🎭 SCENARIO (Optimized Generation):\n{scenario_text}\n\n⚡ Generated using enhanced performance pipeline\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to generate scenario: {error_msg}"
    
    async def _get_campaign_context_async(self):
        """Async campaign context retrieval"""
        response = self._send_message_and_wait("campaign_manager", "get_campaign_context", {}, timeout=5.0)
        if response and response.get("success"):
            return response["context"]
        return {}
    
    async def _get_game_state_async(self):
        """Async game state retrieval"""
        response = self._send_message_and_wait("game_engine", "get_game_state", {}, timeout=5.0)
        if response and response.get("game_state"):
            return response["game_state"]
        return {}
    
    def _create_optimized_context(self, campaign_context: dict, game_state_dict: dict, user_query: str) -> dict:
        """Create optimized context with smart size reduction"""
        optimized_context = {
            'campaign': {},
            'game_state': {},
            'recent_events': []
        }
        
        # Essential campaign info only
        if campaign_context:
            optimized_context['campaign'] = {
                'title': campaign_context.get('title', ''),
                'setting': campaign_context.get('setting', ''),
                'theme': campaign_context.get('theme', '')
            }
        
        # Essential game state info only
        if game_state_dict:
            optimized_context['game_state'] = {
                'current_location': game_state_dict.get('location', ''),
                'scenario_count': game_state_dict.get('scenario_count', 0)
            }
            
            # Include only last 2 events for story continuity (reduced from 3)
            story_progression = game_state_dict.get('story_progression', [])
            if story_progression:
                optimized_context['recent_events'] = story_progression[-2:]
        
        return optimized_context
    
    def _build_enhanced_query(self, user_query: str, optimized_context: dict) -> str:
        """Build enhanced query with optimized context"""
        enhanced_query = self._build_enhanced_scenario_query_with_context(user_query, optimized_context)
        
        # Add turn number as cache buster
        turn_num = optimized_context.get('game_state', {}).get('scenario_count', 0)
        cache_buster = f" (Turn {turn_num})"
        
        return enhanced_query + cache_buster
    
    def _build_enhanced_scenario_query_with_context(self, user_query: str, context: dict) -> str:
        """Build enhanced scenario query with skill checks and combat options"""
        # Extract context information
        campaign = context.get('campaign', {}) if isinstance(context, dict) else {}
        game_state = context.get('game_state', {}) if isinstance(context, dict) else {}
        recent_events = context.get('recent_events', []) if isinstance(context, dict) else []
        
        # Build base query with context
        enhanced_query = f"Continue this D&D adventure story:\n"
        
        if campaign.get('title'):
            enhanced_query += f"Campaign: {campaign['title']}\n"
        if campaign.get('setting'):
            enhanced_query += f"Setting: {campaign['setting']}\n"
        if game_state.get('current_location'):
            enhanced_query += f"Location: {game_state['current_location']}\n"
        
        # Add recent events for continuity
        if recent_events:
            progression_summary = "Recent events: "
            for event in recent_events:
                consequence = event.get('consequence', '')[:80]
                progression_summary += f"{event.get('choice', 'Action')} → {consequence}... "
            enhanced_query += f"{progression_summary}\n"
        
        enhanced_query += f"\nUser Request: {user_query}\n\n"
        
        # Add the critical skill check and combat instructions
        enhanced_query += (
            "Generate an engaging scene continuation (2-3 sentences) and provide 3-4 numbered options for the players.\n\n"
            "IMPORTANT: Include these types of options:\n"
            "- If appropriate to the scene, include 1-2 options that require SKILL CHECKS (Stealth, Perception, Athletics, Persuasion, Investigation, etc.) with clear success/failure consequences\n"
            "- If appropriate to the scene, include potential COMBAT scenarios with specific enemies/monsters\n"
            "- Mix of direct action, social interaction, and problem-solving options\n\n"
            "For skill check options, format like: '1. **Stealth Check (DC 15)** - Sneak past the guards to avoid confrontation'\n"
            "For combat options, format like: '2. **Combat** - Attack the bandits (2 Bandits, 1 Bandit Captain)'\n\n"
            "Ensure options are clearly numbered and formatted for easy selection."
        )
        
        return enhanced_query
    
    def _update_game_state_async(self, user_query: str, scenario_text: str, game_state_dict: dict):
        """Update game state asynchronously to not block response"""
        try:
            # Ensure we have a valid game state dictionary with required fields
            if not game_state_dict:
                game_state_dict = {}
            
            # Initialize required fields if missing
            if "story_progression" not in game_state_dict:
                game_state_dict["story_progression"] = []
            if "scenario_count" not in game_state_dict:
                game_state_dict["scenario_count"] = 0
            if "location" not in game_state_dict:
                game_state_dict["location"] = "Unknown Location"
            
            # Update with new scenario information
            game_state_dict["last_scenario_query"] = user_query
            game_state_dict["last_scenario_text"] = scenario_text
            game_state_dict["scenario_count"] = game_state_dict.get("scenario_count", 0) + 1
            game_state_dict["last_updated"] = __import__('time').time()
            
            # Validate that we have meaningful updates to send
            required_updates = ["last_scenario_query", "last_scenario_text", "scenario_count"]
            has_updates = any(game_state_dict.get(key) for key in required_updates)
            
            if not has_updates:
                if self.verbose:
                    print("⚠️ Async game state update skipped: No meaningful updates to send")
                # Still try to send basic update to prevent "No updates provided" error
                game_state_dict["last_updated"] = __import__('time').time()
                game_state_dict["status"] = "active"
            
            # Use adequate timeout for non-blocking update
            response = self._send_message_and_wait("game_engine", "update_game_state", {
                "updates": game_state_dict,
                "async_update": True  # Flag to indicate this is an async update
            }, timeout=15.0)  # Increased timeout for reliability
            
            if response and response.get("success"):
                if self.verbose:
                    print(f"✅ Async game state updated successfully (scenario #{game_state_dict['scenario_count']})")
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
                if self.verbose:
                    print(f"⚠️ Async game state update failed: {error_msg}")
                    print(f"🔍 Game state dict keys: {list(game_state_dict.keys())}")
                    print(f"🔍 Scenario count: {game_state_dict.get('scenario_count', 0)}")
                    
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Async game state update failed: {e}")
                import traceback
                print(f"🔍 Stack trace: {traceback.format_exc()}")
    
    def _generate_scenario_standard(self, user_query: str) -> str:
        """Standard scenario generation (fallback method)"""
        # Get campaign context if available
        campaign_context = ""
        campaign_response = self._send_message_and_wait("campaign_manager", "get_campaign_context", {})
        if campaign_response and campaign_response.get("success"):
            campaign_context = json.dumps(campaign_response["context"])
        
        # Get current game state if available
        game_state_dict = {}
        game_state = ""
        if self.game_engine_agent:
            state_response = self._send_message_and_wait("game_engine", "get_game_state", {})
            if state_response and state_response.get("game_state"):
                game_state_dict = state_response["game_state"]
                game_state = json.dumps(game_state_dict)
        
        # Build enhanced query that includes story progression context
        enhanced_query = user_query
        if game_state_dict.get("story_progression"):
            recent_events = game_state_dict["story_progression"][-3:]  # Last 3 events
            if recent_events:
                progression_summary = "Recent story events: "
                for event in recent_events:
                    progression_summary += f"Choice: {event['choice']} → {event['consequence'][:100]}... "
                enhanced_query = f"{user_query}\n\nContinue from: {progression_summary}"
                
                if self.verbose:
                    print(f"📖 Enhanced query with story progression context")
        
        # Add timestamp to force new generation even with similar queries
        cache_buster = f" (Turn {len(game_state_dict.get('story_progression', []))})"
        final_query = enhanced_query + cache_buster
        
        # Generate scenario using Haystack pipeline (longer timeout for LLM processing)
        response = self._send_message_and_wait("haystack_pipeline", "query_scenario", {
            "query": final_query,
            "campaign_context": campaign_context,
            "game_state": game_state
        }, timeout=30.0)
        
        if response and response.get("success"):
            result = response["result"]
            scenario_text = result.get("answer", "Failed to generate scenario")
            
            # Check if scenario generation actually failed due to no connection
            if "Pipeline not available" in scenario_text or "not connected" in scenario_text:
                # Provide fallback scenario with proper numbered options when RAG is not available
                fallback_scenario = """The party finds themselves at a crossroads where four paths diverge into the unknown.

**1. Take the North Path** - Follow the well-worn trail toward distant mountains
**2. Take the East Path** - Head through the dense forest where strange sounds echo
**3. Take the West Path** - Follow the river downstream toward civilization
**4. Make Camp Here** - Rest and prepare before choosing a direction"""
                
                # Extract and store the fallback options
                self._extract_and_store_options(fallback_scenario)
                return f"🎭 SCENARIO (Fallback - RAG Offline):\n{fallback_scenario}\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
            else:
                # Extract and store options for later use
                self._extract_and_store_options(scenario_text)
                
                # Update game state to track scenario generation
                if self.game_engine_agent and game_state_dict:
                    game_state_dict["last_scenario_query"] = user_query
                    game_state_dict["last_scenario_text"] = scenario_text
                    game_state_dict["scenario_count"] = game_state_dict.get("scenario_count", 0) + 1
                    
                    response = self._send_message_and_wait("game_engine", "update_game_state", {
                        "updates": game_state_dict
                    }, timeout=15.0)  # Increased timeout for better reliability
                    
                    if not (response and response.get("success")) and self.verbose:
                        error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
                        print(f"⚠️ Standard scenario game state update failed: {error_msg}")
                
                return f"🎭 SCENARIO (Agent-Generated):\n{scenario_text}\n\n🤖 Generated using modular agent architecture\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            # Provide fallback scenario when RAG is not available
            if "not connected" in error_msg or "not available" in error_msg:
                fallback_scenario = """The party finds themselves at a crossroads where four paths diverge into the unknown.

**1. Take the North Path** - Follow the well-worn trail toward distant mountains
**2. Take the East Path** - Head through the dense forest where strange sounds echo
**3. Take the West Path** - Follow the river downstream toward civilization
**4. Make Camp Here** - Rest and prepare before choosing a direction"""
                
                # Extract and store the fallback options
                self._extract_and_store_options(fallback_scenario)
                return f"🎭 SCENARIO (Fallback - RAG Offline):\n{fallback_scenario}\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
            else:
                return f"❌ Failed to generate scenario: {error_msg}"
    
    def _select_player_option(self, option_number: int) -> str:
        """Handle player option selection with skill checks, combat detection, and automatic subsequent scene generation"""
        # Check if we have stored options
        if not self.last_scenario_options:
            # If no options available, generate a quick scenario first
            if self.verbose:
                print("⚠️ No options available, generating scenario first...")
            scenario_response = self._generate_scenario("The party finds themselves in a new situation")
            
            # Check if we now have options after generating scenario
            if not self.last_scenario_options:
                return "❌ Unable to generate scenario options. Please try 'generate scenario' first."
        
        # Validate option number
        if option_number < 1 or option_number > len(self.last_scenario_options):
            return f"❌ Invalid option number. Please choose 1-{len(self.last_scenario_options)}"
        
        # Get the selected option
        selected_option = self.last_scenario_options[option_number - 1]
        
        # Get current game state for context
        game_state = {"current_options": "\n".join(self.last_scenario_options)}
        if self.game_engine_agent:
            state_response = self._send_message_and_wait("game_engine", "get_game_state", {})
            if state_response and state_response.get("game_state"):
                game_state.update(state_response["game_state"])
        
        # DETECT SKILL CHECK OPTIONS
        skill_check_result = self._handle_skill_check_option(selected_option)
        
        # DETECT COMBAT OPTIONS
        combat_result = self._handle_combat_option(selected_option, game_state)
        
        continuation = ""
        
        # Handle skill checks if detected
        if skill_check_result:
            skill_info = skill_check_result
            success_text = "SUCCESS!" if skill_info["success"] else "FAILURE!"
            continuation = f"🎲 **{skill_info['skill'].upper()} CHECK (DC {skill_info['dc']})**\n"
            continuation += f"**Roll:** {skill_info['roll_description']} = **{skill_info['roll_total']}** - {success_text}\n\n"
        
        # Handle combat initialization if detected
        if combat_result:
            combat_info = combat_result
            continuation += f"⚔️ **COMBAT INITIATED!**\n"
            continuation += f"**Enemies:** {', '.join([enemy['name'] for enemy in combat_info['enemies']])}\n\n"
            continuation += "Combat has been automatically set up with all players and enemies.\n"
            continuation += "Use combat commands: 'combat status', 'next turn', 'end combat'\n\n"
        
        # Use scenario generator agent to process the choice
        game_state["current_options"] = "\n".join(self.last_scenario_options)
        
        response = self._send_message_and_wait("scenario_generator", "apply_player_choice", {
            "game_state": game_state,
            "player": "DM",
            "choice": option_number
        }, timeout=30.0)
        
        if response and response.get("success"):
            agent_continuation = response.get("continuation", "Option processed")
            
            # Combine skill/combat results with agent continuation
            if continuation:
                continuation += f"**Story Continues:**\n{agent_continuation}"
            else:
                continuation = agent_continuation
        else:
            # If agent fails, create a basic continuation
            if not continuation:
                continuation = f"You chose: {selected_option}\n\nThe party proceeds with their chosen action..."
        
        # UPDATE GAME STATE WITH CHOICE AND CONSEQUENCE
        updated_game_state = game_state.copy()
        updated_game_state["last_player_choice"] = selected_option
        updated_game_state["last_consequence"] = continuation
        updated_game_state["story_progression"] = updated_game_state.get("story_progression", [])
        
        # Add skill check and combat results to progression
        progression_entry = {
            "choice": selected_option,
            "consequence": continuation,
            "timestamp": __import__('time').time()
        }
        if skill_check_result:
            progression_entry["skill_check"] = skill_check_result
        if combat_result:
            progression_entry["combat_started"] = True
            progression_entry["enemies"] = combat_result["enemies"]
        
        updated_game_state["story_progression"].append(progression_entry)
        
        # Update game engine with new state (with longer timeout and error handling)
        if self.game_engine_agent:
            try:
                update_response = self._send_message_and_wait("game_engine", "update_game_state", {
                    "updates": updated_game_state
                }, timeout=15.0)  # Increased timeout and fixed key name
                
                if not (update_response and update_response.get("success")):
                    if self.verbose:
                        error_msg = update_response.get('error', 'Unknown error') if update_response else 'Timeout'
                        print(f"⚠️ Game state update failed: {error_msg}")
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Exception during game state update: {e}")
        
        if self.verbose:
            print("📝 Updated game state with player choice progression")
        
        # Clear simple cache entries related to scenarios to force new generation
        if self.enable_caching and self.inline_cache:
            # Clean up expired entries to keep cache fresh
            self.inline_cache.cleanup_expired()
        
        # Clear stored options to prevent re-selection
        self.last_scenario_options = []
        
        # AUTOMATICALLY GENERATE SUBSEQUENT SCENE
        if self.verbose:
            print("🔄 Automatically generating subsequent scene...")
        
        # Create a prompt that continues from the consequence
        continuation_prompt = f"Continue the story after: {continuation}"
        
        # Generate the next scenario automatically
        try:
            next_scenario = self._generate_scenario_after_choice(continuation_prompt, updated_game_state if 'updated_game_state' in locals() else game_state)
            
            if next_scenario:
                # Combine the choice consequence with the new scenario
                full_response = f"✅ **SELECTED:** Option {option_number}\n\n🎭 **STORY CONTINUES:**\n{continuation}\n\n"
                full_response += f"📖 **WHAT HAPPENS NEXT:**\n{next_scenario}\n\n"
                full_response += f"📝 *DM: Type 'select option [number]' to choose the next action and continue the story.*"
                
                return full_response
            else:
                # Fallback if scenario generation fails
                return f"✅ **SELECTED:** Option {option_number}\n\n🎭 **STORY CONTINUES:**\n{continuation}\n\n📝 *Use 'generate scenario' to continue the adventure.*"
        
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Automatic scenario generation failed: {e}")
            # Fallback if automatic generation fails
            return f"✅ **SELECTED:** Option {option_number}\n\n🎭 **STORY CONTINUES:**\n{continuation}\n\n📝 *Use 'generate scenario' to continue the adventure.*"
    
    def _generate_scenario_after_choice(self, continuation_prompt: str, game_state: dict) -> str:
        """Generate a scenario that continues after a player choice consequence"""
        try:
            # Get campaign context if available
            campaign_context = ""
            campaign_response = self._send_message_and_wait("campaign_manager", "get_campaign_context", {})
            if campaign_response and campaign_response.get("success"):
                campaign_context = json.dumps(campaign_response["context"])
            
            # Build enhanced query that includes the recent choice and consequence with skill/combat options
            context_dict = {
                'campaign': {'title': '', 'setting': ''},
                'game_state': game_state,
                'recent_events': game_state.get("story_progression", [])[-2:]  # Last 2 events including current
            }
            
            enhanced_query = self._build_enhanced_scenario_query_with_context(continuation_prompt, context_dict)
            
            # Add timestamp to force new generation
            cache_buster = f" (Continue Turn {len(game_state.get('story_progression', []))})"
            final_query = enhanced_query + cache_buster
            
            # Generate scenario using Haystack pipeline
            response = self._send_message_and_wait("haystack_pipeline", "query_scenario", {
                "query": final_query,
                "campaign_context": campaign_context,
                "game_state": json.dumps(game_state)
            }, timeout=25.0)
            
            if response and response.get("success"):
                result = response["result"]
                scenario_text = result.get("answer", "")
                
                # Extract and store options for later use
                self._extract_and_store_options(scenario_text)
                
                # Update game state to track the new scenario generation
                if self.game_engine_agent:
                    game_state["last_scenario_query"] = continuation_prompt
                    game_state["last_scenario_text"] = scenario_text
                    game_state["scenario_count"] = game_state.get("scenario_count", 0) + 1
                    
                    response = self._send_message_and_wait("game_engine", "update_game_state", {
                        "updates": game_state
                    }, timeout=15.0)  # Increased timeout for reliability
                    
                    if not (response and response.get("success")) and self.verbose:
                        error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
                        print(f"⚠️ Scenario after choice game state update failed: {error_msg}")
                
                if self.verbose:
                    print("🔄 Generated subsequent scenario automatically")
                
                return scenario_text
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
                if self.verbose:
                    print(f"⚠️ Failed to generate subsequent scenario: {error_msg}")
                return ""
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error in automatic scenario generation: {e}")
            return ""
    
    def _handle_skill_check_option(self, selected_option: str) -> Optional[Dict[str, Any]]:
        """Handle skill check options and return roll results"""
        import re
        
        # Look for skill check patterns like "**Stealth Check (DC 15)**" or "Stealth Check (DC 15)"
        skill_patterns = [
            r'\*\*([A-Za-z\s]+)\s+Check\s+\(DC\s+(\d+)\)\*\*',  # **Skill Check (DC X)**
            r'([A-Za-z\s]+)\s+Check\s+\(DC\s+(\d+)\)',          # Skill Check (DC X)
            r'\*\*([A-Za-z\s]+)\s+\(DC\s+(\d+)\)\*\*',          # **Skill (DC X)**
        ]
        
        for pattern in skill_patterns:
            match = re.search(pattern, selected_option, re.IGNORECASE)
            if match:
                skill_name = match.group(1).strip().lower()
                dc = int(match.group(2))
                
                if self.verbose:
                    print(f"🎲 Detected skill check: {skill_name} (DC {dc})")
                
                # Roll the skill check
                dice_response = self._send_message_and_wait("dice_system", "roll_dice", {
                    "expression": "1d20",
                    "context": f"{skill_name.title()} Check (DC {dc})",
                    "skill": skill_name
                })
                
                if dice_response and dice_response.get("success"):
                    result = dice_response["result"]
                    total = result.get("total", 0)
                    success = total >= dc
                    
                    return {
                        "type": "skill_check",
                        "skill": skill_name,
                        "dc": dc,
                        "roll_total": total,
                        "success": success,
                        "roll_description": result.get("description", f"Rolled {total}"),
                        "expression": result.get("expression", "1d20")
                    }
        
        return None
    
    def _handle_combat_option(self, selected_option: str, game_state: dict) -> Optional[Dict[str, Any]]:
        """Handle combat options and initialize combat if detected"""
        import re
        
        # Look for combat patterns like "**Combat**" or "Attack the bandits (2 Bandits, 1 Bandit Captain)"
        combat_patterns = [
            r'\*\*Combat\*\*',                                   # **Combat**
            r'Attack\s+.*?\(([^)]+)\)',                         # Attack ... (enemies)
            r'Fight\s+.*?\(([^)]+)\)',                          # Fight ... (enemies)
            r'\*\*Combat\*\*\s*-\s*.*?\(([^)]+)\)',            # **Combat** - ... (enemies)
        ]
        
        for pattern in combat_patterns:
            match = re.search(pattern, selected_option, re.IGNORECASE)
            if match:
                if self.verbose:
                    print(f"⚔️ Detected combat option: {selected_option}")
                
                # Extract enemy information if available
                enemies = []
                if match.groups():
                    enemy_text = match.group(1)
                    # Parse enemy information like "2 Bandits, 1 Bandit Captain"
                    enemy_parts = [part.strip() for part in enemy_text.split(',')]
                    for part in enemy_parts:
                        # Look for patterns like "2 Bandits" or "1 Bandit Captain"
                        enemy_match = re.match(r'(\d+)\s+(.+)', part.strip())
                        if enemy_match:
                            count = int(enemy_match.group(1))
                            enemy_type = enemy_match.group(2).strip()
                            for i in range(count):
                                enemy_name = f"{enemy_type} {i+1}" if count > 1 else enemy_type
                                enemies.append({
                                    "name": enemy_name,
                                    "type": enemy_type,
                                    "max_hp": self._get_enemy_hp(enemy_type),
                                    "armor_class": self._get_enemy_ac(enemy_type)
                                })
                
                # Add all players to combat
                self._setup_combat_with_players_and_enemies(enemies, game_state)
                
                return {
                    "type": "combat",
                    "enemies": enemies,
                    "combat_started": True
                }
        
        return None
    
    def _get_enemy_hp(self, enemy_type: str) -> int:
        """Get default HP for enemy types"""
        enemy_hp_defaults = {
            "bandit": 11,
            "bandit captain": 65,
            "goblin": 7,
            "orc": 15,
            "skeleton": 13,
            "zombie": 22,
            "wolf": 11,
            "guard": 11,
            "cultist": 9,
            "thug": 32
        }
        return enemy_hp_defaults.get(enemy_type.lower(), 15)  # Default 15 HP
    
    def _get_enemy_ac(self, enemy_type: str) -> int:
        """Get default AC for enemy types"""
        enemy_ac_defaults = {
            "bandit": 12,
            "bandit captain": 15,
            "goblin": 15,
            "orc": 13,
            "skeleton": 13,
            "zombie": 8,
            "wolf": 13,
            "guard": 16,
            "cultist": 12,
            "thug": 11
        }
        return enemy_ac_defaults.get(enemy_type.lower(), 12)  # Default 12 AC
    
    def _setup_combat_with_players_and_enemies(self, enemies: List[Dict], game_state: dict):
        """Setup combat by adding all players and enemies to the combat engine"""
        try:
            # Clear any cached combat failures to ensure fresh start
            if self.enable_caching and self.inline_cache:
                self.inline_cache.delete("combat_engine_start_combat_{}")
            
            # FIRST: Add all players from campaign
            players_response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                for player in players_response["players"]:
                    add_response = self._send_message_and_wait("combat_engine", "add_combatant", {
                        "name": player["name"],
                        "max_hp": player.get("hp", 20),
                        "armor_class": player.get("combat_stats", {}).get("armor_class", 12),
                        "is_player": True
                    })
                    if self.verbose and add_response and add_response.get("success"):
                        print(f"📝 Added player {player['name']} to combat")
            
            # SECOND: Add all enemies
            for enemy in enemies:
                add_response = self._send_message_and_wait("combat_engine", "add_combatant", {
                    "name": enemy["name"],
                    "max_hp": enemy["max_hp"],
                    "armor_class": enemy["armor_class"],
                    "is_player": False
                })
                if self.verbose and add_response and add_response.get("success"):
                    print(f"📝 Added enemy {enemy['name']} to combat")
            
            # THIRD: Now start combat (after combatants are added)
            start_response = self._send_message_and_wait("combat_engine", "start_combat", {})
            if not (start_response and start_response.get("success")):
                if self.verbose:
                    error_msg = start_response.get('error', 'Unknown error') if start_response else 'Timeout'
                    print(f"⚠️ Failed to start combat engine: {error_msg}")
                return
            
            if self.verbose:
                player_count = len(players_response.get("players", [])) if players_response else 0
                print(f"⚔️ Combat successfully initialized with {player_count} players and {len(enemies)} enemies")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error setting up combat: {e}")
    
    def _extract_and_store_options(self, scenario_text: str):
        """Extract numbered options from scenario text and store them"""
        import re
        
        options = []
        lines = scenario_text.split('\n')
        
        # Look for multiple patterns of numbered options
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
        
        # If no options found, provide fallback options for continued gameplay
        if not options:
            if self.verbose:
                print(f"⚠️ No options extracted from scenario text, providing fallback options")
            
            # Create generic fallback options based on common D&D actions
            options = [
                "1. Investigate the area more carefully",
                "2. Move forward cautiously",
                "3. Try a different approach",
                "4. Ask your companions for advice"
            ]
        
        self.last_scenario_options = options
        if self.verbose:
            if len(options) <= 4 and all("investigate" in opt.lower() or "move forward" in opt.lower() or "different approach" in opt.lower() or "ask" in opt.lower() for opt in options):
                print(f"📝 Using {len(options)} fallback scenario options")
            else:
                print(f"📝 Stored {len(options)} scenario options for selection")
    
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
    
    def _get_system_status(self) -> str:
        """Get comprehensive system status"""
        status = "🤖 MODULAR DM ASSISTANT STATUS:\n\n"
        
        # Agent status - using consistent format from test expectations
        agent_status = self.orchestrator.get_agent_status()
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
    
    def _handle_general_query(self, instruction: str, params: dict = None) -> str:
        """Handle general queries using RAG with performance optimization"""
        # Extract query from instruction or params
        query = instruction
        if params and 'query' in params:
            query = params['query']
        
        # Use direct RAG for general queries
        response = self._send_message_and_wait("haystack_pipeline", "query_rag", {"query": query}, timeout=15.0)
        
        if response and response.get("success"):
            result = response["result"]
            answer = result.get("answer", "No answer generated")
            
            # Condense the answer if it's too long
            if len(answer) > 800:
                # Find a good break point - preferably end of a sentence or paragraph
                break_point = 800
                for i in range(700, min(800, len(answer))):
                    if answer[i] in '.!?':
                        break_point = i + 1
                        break
                answer = answer[:break_point].strip() + "..."
            
            return f"💡 {answer}"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to process query: {error_msg}"
    
    def _handle_dice_roll(self, instruction: str) -> str:
        """Handle dice rolling commands with enhanced skill detection"""
        import re
        
        # Enhanced skill detection
        skill_keywords = {
            'stealth': ('dexterity', 'stealth'),
            'perception': ('wisdom', 'perception'),
            'insight': ('wisdom', 'insight'),
            'persuasion': ('charisma', 'persuasion'),
            'deception': ('charisma', 'deception'),
            'athletics': ('strength', 'athletics'),
            'acrobatics': ('dexterity', 'acrobatics'),
            'investigation': ('intelligence', 'investigation'),
            'arcana': ('intelligence', 'arcana'),
            'history': ('intelligence', 'history'),
            'nature': ('intelligence', 'nature'),
            'religion': ('intelligence', 'religion'),
            'medicine': ('wisdom', 'medicine'),
            'survival': ('wisdom', 'survival'),
            'animal_handling': ('wisdom', 'animal handling'),
            'intimidation': ('charisma', 'intimidation'),
            'performance': ('charisma', 'performance')
        }
        
        # Detect skill checks more reliably
        instruction_lower = instruction.lower()
        detected_skill = None
        dice_expression = None
        context = "Manual roll"
        
        for skill, (ability, skill_name) in skill_keywords.items():
            if skill in instruction_lower or f"{skill} check" in instruction_lower:
                detected_skill = skill_name
                dice_expression = "1d20"  # Default skill check
                context = f"{skill_name.title()} check ({ability.title()})"
                break
        
        # If no skill detected, extract dice expression from instruction
        if not detected_skill:
            dice_patterns = [
                r'\b(\d*d\d+(?:[kKhHlL]\d+)?(?:[+-]\d+)?(?:\s+(?:adv|advantage|dis|disadvantage))?)\b',
                r'\b(d\d+)\b',  # Simple d20, d6, etc.
                r'\b(\d+d\d+)\b'  # 3d6, 2d8, etc.
            ]
            
            for pattern in dice_patterns:
                match = re.search(pattern, instruction, re.IGNORECASE)
                if match:
                    dice_expression = match.group(1)
                    break
            
            # If no specific dice found, try to infer from context
            if not dice_expression:
                if any(word in instruction.lower() for word in ['attack', 'hit']):
                    dice_expression = "1d20"
                    context = "Attack roll"
                elif any(word in instruction.lower() for word in ['damage', 'hurt']):
                    dice_expression = "1d6"
                    context = "Damage roll"
                elif any(word in instruction.lower() for word in ['stats', 'ability', 'score']):
                    dice_expression = "4d6k3"
                    context = "Ability score generation"
                elif "save" in instruction.lower() or "saving" in instruction.lower():
                    dice_expression = "1d20"
                    context = "Saving throw"
                else:
                    dice_expression = "1d20"  # Default
            else:
                # Add context from instruction for non-skill rolls
                if "attack" in instruction.lower():
                    context = "Attack roll"
                elif "damage" in instruction.lower():
                    context = "Damage roll"
                elif "save" in instruction.lower() or "saving" in instruction.lower():
                    context = "Saving throw"
        
        # Enhanced response formatting
        response = self._send_message_and_wait("dice_system", "roll_dice", {
            "expression": dice_expression,
            "context": context,
            "skill": detected_skill
        })
        
        if response and response.get("success"):
            result = response["result"]
            output = f"🎲 **{context.upper()}**\n"
            output += f"**Expression:** {result['expression']}\n"
            output += f"**Result:** {result['description']}\n"
            
            if detected_skill:
                output += f"**Skill:** {detected_skill.title()}\n"
            
            if result.get('critical_hit'):
                output += "🔥 **CRITICAL HIT!**\n"
            elif result.get('critical_fail'):
                output += "💥 **CRITICAL FAILURE!**\n"
            
            if result.get('advantage_type', 'normal') != 'normal':
                output += f"📊 Rolled with {result['advantage_type']}\n"
            
            return output
        else:
            return f"❌ Failed to roll dice: {response.get('error', 'Unknown error')}"
    
    def _handle_combat_command(self, instruction: str) -> str:
        """Handle combat-related commands"""
        instruction_lower = instruction.lower()
        
        # Start combat with auto-populated combatants
        if "start combat" in instruction_lower or "begin combat" in instruction_lower:
            # First, try to add players as combatants
            players_response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                for player in players_response["players"]:
                    # Ensure numeric values are integers, not strings
                    max_hp = int(player.get("hp", 20)) if str(player.get("hp", 20)).isdigit() else 20
                    armor_class = int(player.get("combat_stats", {}).get("armor_class", 12)) if str(player.get("combat_stats", {}).get("armor_class", 12)).isdigit() else 12
                    
                    self._send_message_and_wait("combat_engine", "add_combatant", {
                        "name": player["name"],
                        "max_hp": max_hp,
                        "armor_class": armor_class,
                        "is_player": True
                    })
                    if self.verbose:
                        print(f"📝 Added {player['name']} to combat (HP: {max_hp}, AC: {armor_class})")
            
            # Add some default enemies if no players available
            else:
                default_combatants = [
                    {"name": "Bandit", "max_hp": 11, "armor_class": 12, "is_player": False},
                    {"name": "Guard", "max_hp": 11, "armor_class": 16, "is_player": False}
                ]
                for combatant in default_combatants:
                    self._send_message_and_wait("combat_engine", "add_combatant", combatant)
                    if self.verbose:
                        print(f"📝 Added {combatant['name']} to combat")
            
            # Now start combat
            response = self._send_message_and_wait("combat_engine", "start_combat", {})
            if response and response.get("success"):
                output = "⚔️ **COMBAT STARTED!**\n\n"
                output += "📊 **Initiative Order:**\n"
                
                # Fix unpacking error - handle different initiative_order formats
                initiative_order = response.get("initiative_order", [])
                for item in initiative_order:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            name, init = item[0], item[1]
                            output += f"  • {name}: {init}\n"
                        elif isinstance(item, dict):
                            name = item.get('name', 'Unknown')
                            init = item.get('initiative', item.get('init', 'N/A'))
                            output += f"  • {name}: {init}\n"
                        else:
                            output += f"  • {str(item)}\n"
                    except (ValueError, TypeError, IndexError) as e:
                        if self.verbose:
                            print(f"⚠️ Initiative order unpacking error: {e}")
                        output += f"  • {str(item)}\n"
                
                current = response.get("current_combatant")
                if current:
                    output += f"\n🎯 **Current Turn:** {current['name']}\n"
                
                return output
            else:
                return f"❌ Failed to start combat: {response.get('error', 'Combat initialization failed')}"
        
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
        
        # Next turn - Enhanced with improved error handling
        elif "next turn" in instruction_lower or "end turn" in instruction_lower:
            # Enhanced combat turn management with better error handling
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self._send_message_and_wait("combat_engine", "next_turn", {}, timeout=10.0)
                    if response and response.get("success"):
                        output = f"🔄 {response.get('message', 'Turn advanced')}\n"
                        current = response.get("current_combatant")
                        if current:
                            output += f"🎯 **Now active:** {current['name']} ({current['hp']} HP)"
                        
                        # Broadcast turn change to maintain agent synchronization
                        if current and self.orchestrator:
                            try:
                                self.orchestrator.broadcast_event("combat_turn_changed", {
                                    "current_combatant": current,
                                    "round": response.get("round", 1)
                                })
                                if self.verbose:
                                    print("📡 Broadcasted turn change to all agents")
                            except Exception as e:
                                if self.verbose:
                                    print(f"⚠️ Failed to broadcast turn change: {e}")
                        
                        return output
                    else:
                        error_msg = response.get('error', 'Turn management failed') if response else 'Agent communication timeout'
                        
                        # Provide more helpful error messages
                        if "not active" in error_msg.lower():
                            if attempt == max_retries - 1:
                                return f"❌ Combat is not active. Use 'start combat' to begin a new encounter."
                        elif "no combatants" in error_msg.lower():
                            if attempt == max_retries - 1:
                                return f"❌ No combatants in combat. Use 'start combat' to add combatants automatically."
                        else:
                            if attempt == max_retries - 1:
                                return f"❌ Failed to advance turn: {error_msg}"
                        
                        if self.verbose:
                            print(f"⚠️ Turn management attempt {attempt + 1} failed: {error_msg}, retrying...")
                        
                except Exception as e:
                    error_msg = f"Turn management exception: {e}"
                    if attempt == max_retries - 1:
                        return f"❌ Failed to advance turn after {max_retries} attempts: {error_msg}"
                    elif self.verbose:
                        print(f"⚠️ Turn management attempt {attempt + 1} failed: {error_msg}, retrying...")
                
                # Brief pause before retry
                import time
                time.sleep(0.5)
            
            return f"❌ Failed to advance turn after {max_retries} attempts"
        
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
        """Handle rule checking with enhanced error recovery and performance optimization"""
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
        
        # Enhanced condition lookup with better pattern matching
        conditions = ["blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
                     "invisible", "paralyzed", "poisoned", "prone", "restrained", "stunned", "unconscious"]
        
        condition_found = None
        # Check for direct condition mentions or "what happens when X" patterns
        for condition in conditions:
            if (condition in query or
                f"when {condition}" in query or
                f"{condition} condition" in query or
                f"happens when {condition}" in query):
                condition_found = condition
                break
        
        if condition_found:
            response = self._send_message_and_wait("rule_enforcement", "get_condition_effects", {
                "condition_name": condition_found
            }, timeout=8.0)  # Reduced timeout for faster response
            
            if response and response.get("success"):
                effects = response["effects"]
                output = f"📖 **{condition_found.upper()} CONDITION**\n\n"
                output += "**Effects:**\n"
                for effect in effects.get("effects", []):
                    output += f"• {effect}\n"
                output += f"\n**Duration:** {effects.get('duration', 'Unknown')}\n"
                return output
        
        # Try direct rule query with reduced timeout
        response = self._send_message_and_wait("rule_enforcement", "check_rule", {
            "query": query,
            "category": category
        }, timeout=8.0)  # Reduced timeout for faster response
        
        if response and response.get("success"):
            rule_info = response["rule_info"]
            output = f"📖 **{category.upper()} RULE**\n\n"
            output += f"**Rule:** {rule_info['rule_text']}\n\n"
            
            if rule_info.get("sources"):
                sources = rule_info['sources']
                if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                    source_names = [source.get('source', str(source)) for source in sources]
                else:
                    source_names = sources if isinstance(sources, list) else [str(sources)]
                output += f"**Sources:** {', '.join(source_names)}\n"
            
            confidence = rule_info.get("confidence", "medium")
            confidence_emoji = {"high": "🔍", "medium": "📚", "low": "❓"}
            output += f"**Confidence:** {confidence_emoji.get(confidence, '📚')} {confidence}\n"
            
            return output
        
        # Fallback if rule query fails
        error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
        return f"❌ Failed to find rule: {error_msg}"
    
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
                        # Get file modification time
                        mod_time = os.path.getmtime(filepath)
                        mod_date = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M")
                        
                        # Try to read save metadata
                        with open(filepath, 'r') as f:
                            save_data = json.load(f)
                        
                        saves.append({
                            'filename': filename,
                            'filepath': filepath,
                            'save_name': save_data.get('save_name', filename[:-5]),  # Remove .json
                            'campaign': save_data.get('campaign_info', {}).get('title', 'Unknown Campaign'),
                            'last_modified': mod_date,
                            'scenario_count': save_data.get('game_state', {}).get('scenario_count', 0),
                            'players': len(save_data.get('players', [])),
                            'story_progression': len(save_data.get('game_state', {}).get('story_progression', []))
                        })
                    except (json.JSONDecodeError, IOError) as e:
                        if self.verbose:
                            print(f"⚠️ Could not read save file {filename}: {e}")
                        continue
            
            # Sort by last modified date (newest first)
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
                if self.verbose:
                    print(f"❌ Save file not found: {save_file}")
                return False
            
            with open(filepath, 'r') as f:
                self.game_save_data = json.load(f)
            
            # Restore game state to game engine
            if self.game_engine_agent and self.game_save_data.get('game_state'):
                response = self._send_message_and_wait("game_engine", "update_game_state", {
                    "updates": self.game_save_data['game_state']
                }, timeout=20.0)  # Even longer timeout for loading game saves
                
                if not (response and response.get("success")) and self.verbose:
                    error_msg = response.get('error', 'Unknown error') if response else 'Timeout'
                    print(f"⚠️ Game save restore failed: {error_msg}")
            
            # Restore last scenario options
            if self.game_save_data.get('last_scenario_options'):
                self.last_scenario_options = self.game_save_data['last_scenario_options']
            
            if self.verbose:
                save_name = self.game_save_data.get('save_name', save_file)
                campaign = self.game_save_data.get('campaign_info', {}).get('title', 'Unknown')
                print(f"💾 Successfully loaded save: {save_name} (Campaign: {campaign})")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error loading save file {save_file}: {e}")
            return False
    
    def _save_game(self, save_name: str, update_existing: bool = False) -> bool:
        """Save the current game state"""
        try:
            # Generate filename
            if update_existing and self.current_save_file:
                filename = self.current_save_file
            else:
                # Create new save file
                safe_name = "".join(c for c in save_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{safe_name}_{timestamp}.json"
            
            filepath = os.path.join(self.game_saves_dir, filename)
            
            # Gather current game state
            current_game_state = {}
            if self.game_engine_agent:
                state_response = self._send_message_and_wait("game_engine", "get_game_state", {})
                if state_response and state_response.get("game_state"):
                    current_game_state = state_response["game_state"]
            
            # Gather campaign info
            campaign_info = {}
            campaign_response = self._send_message_and_wait("campaign_manager", "get_campaign_info", {})
            if campaign_response and campaign_response.get("success"):
                campaign_info = campaign_response["campaign"]
            
            # Gather players info
            players_info = []
            players_response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                players_info = players_response["players"]
            
            # Gather combat state if active
            combat_state = {}
            if self.combat_agent:
                combat_response = self._send_message_and_wait("combat_engine", "get_combat_status", {})
                if combat_response and combat_response.get("success"):
                    combat_state = combat_response["status"]
            
            # Create save data structure
            save_data = {
                'save_name': save_name,
                'save_date': datetime.now().isoformat(),
                'version': '1.0',
                'game_state': current_game_state,
                'campaign_info': campaign_info,
                'players': players_info,
                'combat_state': combat_state,
                'last_scenario_options': self.last_scenario_options,
                'assistant_config': {
                    'collection_name': self.collection_name,
                    'campaigns_dir': self.campaigns_dir,
                    'players_dir': self.players_dir,
                    'enable_game_engine': self.enable_game_engine,
                    'enable_caching': self.enable_caching,
                    'enable_async': self.enable_async
                }
            }
            
            # Write save file
            with open(filepath, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            # Update current save file reference
            self.current_save_file = filename
            self.game_save_data = save_data
            
            if self.verbose:
                print(f"💾 Successfully saved game: {save_name} ({filename})")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error saving game: {e}")
            return False
    
    def _extract_params(self, instruction: str) -> dict:
        """Extract parameters from instruction for save/load commands"""
        words = instruction.split()
        params = {}
        
        # For commands like "save game MyGame" or "load save 1"
        if len(words) >= 3:
            params['param_1'] = words[2]
        
        return params

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
                    
                    # Remove hardcoded help - let it go through normal command processing
                    
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
        
        # Check for existing game saves and offer to load them
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
                            'scenario_count': save_data.get('game_state', {}).get('scenario_count', 0),
                        })
                    except (json.JSONDecodeError, IOError):
                        continue
            
            # Sort by last modified date (newest first)
            saves.sort(key=lambda x: x['last_modified'], reverse=True)
            
            if saves:
                print("\n💾 EXISTING GAME SAVES FOUND:")
                print("0. Start New Campaign")
                for i, save in enumerate(saves, 1):
                    print(f"{i}. {save['save_name']} - {save['campaign']} ({save['last_modified']}) - {save['scenario_count']} scenarios")
                
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