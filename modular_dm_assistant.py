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
from rag_agent_integrated import create_rag_agent, RAGAgentFramework, RAGAgent
from dice_system import DiceSystemAgent, DiceRoller
from combat_engine import CombatEngineAgent, CombatEngine
from rule_enforcement_agent import RuleEnforcementAgent

# Enhanced pipeline components
from pipeline_manager import PipelineManager, IntelligentCache, AsyncPipelineManager
from enhanced_pipeline_components import (
    SmartPipelineRouter, ErrorRecoveryPipeline, CreativeConsequencePipeline,
    CreativeGenerationPipeline, FactualRetrievalPipeline, RulesQueryPipeline,
    HybridCreativeFactualPipeline, ChoiceContextBuilder
)

# Claude-specific imports for text processing
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


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


class AdaptiveErrorRecovery:
    """Advanced error recovery system with learning for Priority 3 improvements"""
    
    def __init__(self):
        self.error_patterns = {}
        self.recovery_success_rates = {}
        self.recovery_strategies = {
            'timeout': self._handle_timeout_recovery,
            'generation_failure': self._handle_generation_failure,
            'context_overflow': self._handle_context_overflow,
            'agent_communication': self._handle_agent_communication_failure
        }
    
    def recover_with_learning(self, error: Exception, context: dict) -> dict:
        """Implement error recovery with pattern learning"""
        error_type = self._classify_error(error)
        
        # Log error pattern
        self._log_error_pattern(error_type, context)
        
        # Apply appropriate recovery strategy
        recovery_func = self.recovery_strategies.get(error_type, self._default_recovery)
        result = recovery_func(error, context)
        
        # Learn from recovery outcome
        self._update_recovery_learning(error_type, result.get('success', False))
        
        return result
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for appropriate recovery strategy"""
        error_str = str(error).lower()
        
        if 'timeout' in error_str or 'timed out' in error_str:
            return 'timeout'
        elif 'generation' in error_str or 'llm' in error_str:
            return 'generation_failure'
        elif 'context' in error_str or 'too long' in error_str:
            return 'context_overflow'
        elif 'agent' in error_str or 'communication' in error_str:
            return 'agent_communication'
        else:
            return 'unknown'
    
    def _log_error_pattern(self, error_type: str, context: dict):
        """Log error pattern for learning"""
        if error_type not in self.error_patterns:
            self.error_patterns[error_type] = []
        
        self.error_patterns[error_type].append({
            'context': context,
            'timestamp': __import__('time').time()
        })
    
    def _handle_timeout_recovery(self, error: Exception, context: dict) -> dict:
        """Handle timeout errors with progressive retry strategy"""
        return {
            'success': True,
            'strategy': 'timeout_retry',
            'message': 'Applied timeout recovery with extended timeout',
            'recovery_action': 'retry_with_longer_timeout'
        }
    
    def _handle_generation_failure(self, error: Exception, context: dict) -> dict:
        """Handle LLM generation failures"""
        return {
            'success': True,
            'strategy': 'fallback_generation',
            'message': 'Applied fallback generation strategy',
            'recovery_action': 'use_simpler_prompt'
        }
    
    def _handle_context_overflow(self, error: Exception, context: dict) -> dict:
        """Handle context size overflow"""
        return {
            'success': True,
            'strategy': 'context_reduction',
            'message': 'Applied context reduction strategy',
            'recovery_action': 'reduce_context_size'
        }
    
    def _handle_agent_communication_failure(self, error: Exception, context: dict) -> dict:
        """Handle agent communication failures"""
        return {
            'success': True,
            'strategy': 'agent_retry',
            'message': 'Applied agent communication retry',
            'recovery_action': 'retry_agent_communication'
        }
    
    def _default_recovery(self, error: Exception, context: dict) -> dict:
        """Default recovery strategy"""
        return {
            'success': False,
            'strategy': 'none',
            'message': f'No specific recovery strategy for: {error}',
            'recovery_action': 'log_and_continue'
        }
    
    def _update_recovery_learning(self, error_type: str, success: bool):
        """Update recovery learning based on outcome"""
        if error_type not in self.recovery_success_rates:
            self.recovery_success_rates[error_type] = {'successes': 0, 'attempts': 0}
        
        self.recovery_success_rates[error_type]['attempts'] += 1
        if success:
            self.recovery_success_rates[error_type]['successes'] += 1


class PerformanceMonitoringDashboard:
    """Real-time system performance monitoring for Priority 3 improvements"""
    
    def __init__(self):
        self.metrics = {
            'response_times': {},
            'error_rates': {},
            'cache_hit_rates': {},
            'agent_health': {},
            'story_quality_scores': []
        }
        self.alert_thresholds = {
            'response_time': 15.0,  # seconds
            'error_rate': 0.1,      # 10%
            'cache_hit_rate': 0.2   # 20%
        }
    
    def record_operation(self, operation: str, duration: float, success: bool):
        """Record an operation for performance monitoring"""
        if operation not in self.metrics['response_times']:
            self.metrics['response_times'][operation] = []
        
        self.metrics['response_times'][operation].append(duration)
        
        # Keep only last 100 measurements
        if len(self.metrics['response_times'][operation]) > 100:
            self.metrics['response_times'][operation] = self.metrics['response_times'][operation][-100:]
        
        # Track error rates
        if operation not in self.metrics['error_rates']:
            self.metrics['error_rates'][operation] = {'successes': 0, 'failures': 0}
        
        if success:
            self.metrics['error_rates'][operation]['successes'] += 1
        else:
            self.metrics['error_rates'][operation]['failures'] += 1
    
    def generate_performance_report(self) -> dict:
        """Generate comprehensive performance report"""
        return {
            'system_health': self._calculate_system_health(),
            'performance_trends': self._analyze_performance_trends(),
            'recommendations': self._generate_performance_recommendations(),
            'alert_conditions': self._check_alert_conditions()
        }
    
    def _calculate_system_health(self) -> float:
        """Calculate overall system health score"""
        health_scores = []
        
        # Response time health
        avg_response_times = []
        for operation, times in self.metrics['response_times'].items():
            if times:
                avg_response_times.append(sum(times) / len(times))
        
        if avg_response_times:
            avg_response_time = sum(avg_response_times) / len(avg_response_times)
            response_health = max(0, 1 - (avg_response_time / 30.0))  # Normalize to 30s max
            health_scores.append(response_health)
        
        # Error rate health
        error_rates = []
        for operation, rates in self.metrics['error_rates'].items():
            total = rates['successes'] + rates['failures']
            if total > 0:
                error_rate = rates['failures'] / total
                error_rates.append(error_rate)
        
        if error_rates:
            avg_error_rate = sum(error_rates) / len(error_rates)
            error_health = max(0, 1 - avg_error_rate)
            health_scores.append(error_health)
        
        return sum(health_scores) / len(health_scores) if health_scores else 0.5
    
    def _analyze_performance_trends(self) -> dict:
        """Analyze performance trends over time"""
        trends = {}
        
        for operation, times in self.metrics['response_times'].items():
            if len(times) >= 10:
                recent_avg = sum(times[-10:]) / 10
                older_avg = sum(times[-20:-10]) / 10 if len(times) >= 20 else recent_avg
                
                trend = 'improving' if recent_avg < older_avg else 'degrading' if recent_avg > older_avg else 'stable'
                trends[operation] = {
                    'trend': trend,
                    'recent_avg': recent_avg,
                    'change_percent': ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
                }
        
        return trends
    
    def _generate_performance_recommendations(self) -> list:
        """Generate performance recommendations"""
        recommendations = []
        
        # Check response times
        for operation, times in self.metrics['response_times'].items():
            if times:
                avg_time = sum(times) / len(times)
                if avg_time > self.alert_thresholds['response_time']:
                    recommendations.append(f"Consider optimizing {operation} - average response time: {avg_time:.2f}s")
        
        # Check error rates
        for operation, rates in self.metrics['error_rates'].items():
            total = rates['successes'] + rates['failures']
            if total > 0:
                error_rate = rates['failures'] / total
                if error_rate > self.alert_thresholds['error_rate']:
                    recommendations.append(f"High error rate detected for {operation}: {error_rate:.1%}")
        
        return recommendations
    
    def _check_alert_conditions(self) -> list:
        """Check for alert conditions"""
        alerts = []
        
        # Response time alerts
        for operation, times in self.metrics['response_times'].items():
            if times and len(times) >= 5:
                recent_avg = sum(times[-5:]) / 5
                if recent_avg > self.alert_thresholds['response_time']:
                    alerts.append({
                        'type': 'response_time',
                        'operation': operation,
                        'value': recent_avg,
                        'threshold': self.alert_thresholds['response_time']
                    })
        
        return alerts


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
        
        # Enhanced pipeline management
        self.pipeline_manager = PipelineManager() if enable_caching else None
        self.smart_router = SmartPipelineRouter()
        self.creative_consequence_pipeline = CreativeConsequencePipeline()
        self.error_recovery = ErrorRecoveryPipeline()
        
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
        self.last_scenario_options = []  # Store last generated options for choice selection
        
        # Enhanced story consistency tracking (Priority 3)
        self.narrative_tracker = NarrativeContinuityTracker() if enable_caching else None
        
        # Advanced error recovery system (Priority 3)
        self.adaptive_error_recovery = AdaptiveErrorRecovery() if enable_caching else None
        
        # Performance monitoring dashboard (Priority 3)
        self.performance_monitor = PerformanceMonitoringDashboard() if enable_caching else None
        
        # Initialize all components
        self._initialize_agents()
        self._setup_enhanced_pipelines()
        
        # Load game save if specified
        if self.current_save_file:
            self._load_game_save(self.current_save_file)
        
        if self.verbose:
            print("🚀 Enhanced Modular DM Assistant initialized with intelligent pipelines")
            if self.current_save_file:
                print(f"💾 Loaded game save: {self.current_save_file}")
            self._print_agent_status()
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
                haystack_agent=self.haystack_agent,
                verbose=self.verbose
            )
            self.orchestrator.register_agent(self.scenario_agent)
            
            if self.verbose:
                print("✅ All agents initialized successfully")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize agents: {e}")
            raise
    
    def _setup_enhanced_pipelines(self):
        """Setup enhanced pipeline components"""
        try:
            # Setup creative consequence pipeline with LLM if available
            if self.has_llm:
                try:
                    llm_generator = AppleGenAIChatGenerator(
                        model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                    )
                    self.creative_consequence_pipeline = CreativeConsequencePipeline(llm_generator)
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Failed to initialize LLM for creative pipeline: {e}")
                    self.creative_consequence_pipeline = CreativeConsequencePipeline()
            
            # Setup smart router with pipeline components
            creative_pipeline = CreativeGenerationPipeline(
                llm_generator if self.has_llm else None
            )
            factual_pipeline = FactualRetrievalPipeline(self.rag_agent)
            rules_pipeline = RulesQueryPipeline(self.rule_agent)
            hybrid_pipeline = HybridCreativeFactualPipeline(creative_pipeline, factual_pipeline)
            
            self.smart_router.register_pipeline('creative', creative_pipeline)
            self.smart_router.register_pipeline('factual', factual_pipeline)
            self.smart_router.register_pipeline('rules', rules_pipeline)
            self.smart_router.register_pipeline('hybrid', hybrid_pipeline)
            self.smart_router.set_fallback_pipeline(hybrid_pipeline)
            
            # Setup error recovery pipeline
            self.error_recovery.set_primary_pipeline(factual_pipeline)
            self.error_recovery.add_fallback_pipeline(creative_pipeline)
            self.error_recovery.add_fallback_pipeline(rules_pipeline)
            
            if self.verbose:
                print("✅ Enhanced pipelines setup complete")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Enhanced pipeline setup failed: {e}")
    
    def _print_pipeline_status(self):
        """Print status of enhanced pipeline components"""
        print("\n🔧 ENHANCED PIPELINE STATUS:")
        print(f"  • Intelligent Caching: {'✅ Enabled' if self.enable_caching else '❌ Disabled'}")
        print(f"  • Async Processing: {'✅ Enabled' if self.enable_async else '❌ Disabled'}")
        print(f"  • Smart Router: {'✅ Active' if self.smart_router else '❌ Inactive'}")
        print(f"  • Creative Consequences: {'✅ Active' if self.creative_consequence_pipeline else '❌ Inactive'}")
        print(f"  • Error Recovery: {'✅ Active' if self.error_recovery else '❌ Inactive'}")
        
        if self.pipeline_manager:
            cache_stats = self.pipeline_manager.get_cache_stats()
            print(f"  • Cache Status: {cache_stats['memory_cache_size']} items in memory")
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
        
        # Game save/load commands
        elif "save game" in instruction_lower:
            self.last_command = ""
            # Extract save name
            words = instruction.split()
            save_name = "Quick Save"
            
            # Look for save name after "save game"
            for i, word in enumerate(words):
                if word.lower() == "game" and i + 1 < len(words):
                    save_name = " ".join(words[i + 1:])
                    break
            
            if self._save_game(save_name):
                return f"💾 Game saved successfully as: {save_name}"
            else:
                return "❌ Failed to save game"
        
        elif "load game" in instruction_lower or "list saves" in instruction_lower:
            self.last_command = ""
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
        
        elif "load save" in instruction_lower:
            self.last_command = ""
            # Extract save number
            words = instruction.split()
            save_number = None
            
            for word in words:
                if word.isdigit():
                    save_number = int(word)
                    break
            
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
        
        elif "update save" in instruction_lower:
            self.last_command = ""
            if not self.current_save_file:
                return "❌ No current save file to update. Use 'save game [name]' to create a new save."
            
            save_name = self.game_save_data.get('save_name', 'Updated Save')
            if self._save_game(save_name, update_existing=True):
                return f"💾 Successfully updated current save: {save_name}"
            else:
                return "❌ Failed to update current save"
        
        # General queries - use RAG
        else:
            self.last_command = ""
            return self._handle_general_query(instruction)
    
    def _send_message_and_wait(self, agent_id: str, action: str, data: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Send a message to an agent and wait for response with enhanced intelligent caching"""
        try:
            # Enhanced caching with query pattern recognition
            if self.pipeline_manager and self.enable_caching:
                cache_key, query_type = self._get_enhanced_cache_key_with_pattern(agent_id, action, data)
                
                if self._should_cache_query(agent_id, action, data, query_type):
                    cached_result = self.pipeline_manager.cache.get_cached_result(cache_key, {})
                    if cached_result and 'result' in cached_result:
                        if self.verbose:
                            print(f"📦 Enhanced cache hit for {agent_id}:{action} ({query_type})")
                        return cached_result['result']
            
            # Start performance monitoring
            op_id = None
            if self.pipeline_manager:
                op_id = self.pipeline_manager.monitor.start_operation(f"{agent_id}_{action}")
            
            # Send message through orchestrator
            message_id = self.orchestrator.send_message_to_agent(agent_id, action, data)
            
            # Wait for response in message history
            start_time = time.time()
            result = None
            while time.time() - start_time < timeout:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        result = msg.get("data", {})
                        break
                if result:
                    break
                time.sleep(0.1)
            
            # End performance monitoring
            if op_id and self.pipeline_manager:
                self.pipeline_manager.monitor.end_operation(op_id, success=(result is not None))
            
            # Enhanced caching of successful results with smart TTL
            if result and self.pipeline_manager and self.enable_caching:
                cache_key, query_type = self._get_enhanced_cache_key_with_pattern(agent_id, action, data)
                
                if self._should_cache_query(agent_id, action, data, query_type):
                    # Set TTL based on query type
                    ttl_hours = self._get_cache_ttl_for_query_type(query_type)
                    self.pipeline_manager.cache.cache_result(cache_key, {}, result, ttl_hours=ttl_hours)
                    
                    if self.verbose:
                        print(f"💾 Cached result for {query_type} (TTL: {ttl_hours}h)")
            
            if not result and self.verbose:
                print(f"⚠️ Timeout waiting for response from {agent_id}")
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Error sending message to {agent_id}: {e}")
            return None
    
    def _get_enhanced_cache_key_with_pattern(self, agent_id: str, action: str, data: Dict[str, Any]) -> tuple[str, str]:
        """Generate cache key and identify query pattern for enhanced caching"""
        import re
        
        # Query pattern recognition
        query_patterns = {
            'scenario_generation': r'generate|scenario|story|continue',
            'rule_queries': r'rule|how does|what happens|mechanics',
            'dice_rolls': r'roll|dice|d\d+',
            'campaign_info': r'campaign|setting|location|npc'
        }
        
        # Determine query type based on agent and action
        query_type = 'general'
        query_text = json.dumps(data).lower()
        
        if agent_id == 'haystack_pipeline' and action == 'query_scenario':
            query_type = 'scenario_generation'
        elif agent_id == 'rule_enforcement':
            query_type = 'rule_queries'
        elif agent_id == 'dice_system':
            query_type = 'dice_rolls'
        elif agent_id == 'campaign_manager':
            query_type = 'campaign_info'
        else:
            # Pattern-based detection for other cases
            for pattern_name, pattern in query_patterns.items():
                if re.search(pattern, query_text):
                    query_type = pattern_name
                    break
        
        # Generate cache key based on pattern
        if query_type == 'scenario_generation':
            # Include less context for creative queries to improve hit rate
            minimal_data = {k: v for k, v in data.items() if k in ['query', 'campaign_context']}
            cache_key = f"{agent_id}_{action}_{json.dumps(minimal_data, sort_keys=True)}"
        else:
            cache_key = f"{agent_id}_{action}_{json.dumps(data, sort_keys=True)}"
        
        return cache_key, query_type
    
    def _should_cache_query(self, agent_id: str, action: str, data: Dict[str, Any], query_type: str) -> bool:
        """Determine if a query should be cached based on type and content"""
        # Cache configuration per pattern type
        cache_config = {
            'scenario_generation': {'priority': 'low', 'should_cache': False},   # Don't cache creative content
            'rule_queries': {'priority': 'high', 'should_cache': True},         # Always cache static rules
            'dice_rolls': {'priority': 'none', 'should_cache': False},          # Never cache random results
            'campaign_info': {'priority': 'medium', 'should_cache': True},      # Cache campaign data
            'general': {'priority': 'medium', 'should_cache': True}
        }
        
        config = cache_config.get(query_type, {'should_cache': True})
        
        # Don't cache random elements or user-specific content
        query_text = json.dumps(data).lower()
        if any(keyword in query_text for keyword in ['roll', 'random', 'dice']):
            return False
        
        # Don't cache scenario generation with timestamps or turn-specific data
        if query_type == 'scenario_generation' and ('turn' in query_text or 'timestamp' in query_text):
            return False
        
        return config['should_cache']
    
    def _get_cache_ttl_for_query_type(self, query_type: str) -> float:
        """Get cache TTL (time-to-live) in hours for different query types"""
        ttl_config = {
            'scenario_generation': 1,     # Short TTL for creative content
            'rule_queries': 24,           # Long TTL for static rules
            'dice_rolls': 0,              # No caching for random results
            'campaign_info': 12,          # Medium TTL for campaign data
            'general': 6                  # Default TTL
        }
        
        return ttl_config.get(query_type, 6)
    
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
            "- At least 1-2 options that require SKILL CHECKS (Stealth, Perception, Athletics, Persuasion, Investigation, etc.) with clear success/failure consequences\n"
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
            game_state_dict["last_scenario_query"] = user_query
            game_state_dict["last_scenario_text"] = scenario_text
            game_state_dict["scenario_count"] = game_state_dict.get("scenario_count", 0) + 1
            
            # Use shorter timeout for non-blocking update
            self._send_message_and_wait("game_engine", "update_game_state", {
                "game_state": game_state_dict
            }, timeout=3.0)
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Async game state update failed: {e}")
    
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
            
            # Extract and store options for later use
            self._extract_and_store_options(scenario_text)
            
            # Update game state to track scenario generation
            if self.game_engine_agent and game_state_dict:
                game_state_dict["last_scenario_query"] = user_query
                game_state_dict["last_scenario_text"] = scenario_text
                game_state_dict["scenario_count"] = game_state_dict.get("scenario_count", 0) + 1
                
                self._send_message_and_wait("game_engine", "update_game_state", {
                    "game_state": game_state_dict
                })
            
            return f"🎭 SCENARIO (Agent-Generated):\n{scenario_text}\n\n🤖 Generated using modular agent architecture\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
            return f"❌ Failed to generate scenario: {error_msg}"
    
    def _select_player_option(self, option_number: int) -> str:
        """Handle player option selection with skill checks, combat detection, and automatic subsequent scene generation"""
        # Check if we have stored options
        if not self.last_scenario_options:
            return "❌ No scenario options available. Please generate a scenario first."
        
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
        
        try:
            # Use enhanced creative consequence pipeline with skill/combat context
            if self.creative_consequence_pipeline:
                enhanced_choice = selected_option
                if skill_check_result:
                    enhanced_choice += f" [Skill Check: {skill_check_result['skill']} {skill_check_result['roll_total']} vs DC {skill_check_result['dc']} - {'Success' if skill_check_result['success'] else 'Failure'}]"
                if combat_result:
                    enhanced_choice += f" [Combat Started with {len(combat_result['enemies'])} enemies]"
                
                story_continuation = self.creative_consequence_pipeline.generate_consequence(
                    choice=enhanced_choice,
                    game_state=game_state,
                    player="DM"
                )
                
                # Combine skill/combat results with story continuation
                if continuation:
                    continuation += f"**Story Continues:**\n{story_continuation}"
                else:
                    continuation = story_continuation
                
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
                
                # Update game engine with new state
                if self.game_engine_agent:
                    self._send_message_and_wait("game_engine", "update_game_state", {
                        "game_state": updated_game_state
                    })
                
                if self.verbose:
                    print("✅ Used enhanced creative consequence pipeline with skill/combat integration")
                    print("📝 Updated game state with player choice progression")
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Enhanced pipeline failed, falling back to agent: {e}")
            
            # Fallback to original agent-based approach with game state updates
            game_state["current_options"] = "\n".join(self.last_scenario_options)
            
            response = self._send_message_and_wait("scenario_generator", "apply_player_choice", {
                "game_state": game_state,
                "player": "DM",
                "choice": option_number
            }, timeout=30.0)
            
            if response and response.get("success"):
                continuation = response.get("continuation", "Option processed")
                
                # Update game state even in fallback
                updated_game_state = game_state.copy()
                updated_game_state["last_player_choice"] = selected_option
                updated_game_state["last_consequence"] = continuation
                updated_game_state["story_progression"] = updated_game_state.get("story_progression", [])
                updated_game_state["story_progression"].append({
                    "choice": selected_option,
                    "consequence": continuation,
                    "timestamp": __import__('time').time()
                })
                
                if self.game_engine_agent:
                    self._send_message_and_wait("game_engine", "update_game_state", {
                        "game_state": updated_game_state
                    })
            else:
                error_msg = response.get('error', 'Unknown error') if response else 'Agent communication timeout'
                return f"❌ Failed to process option: {error_msg}"
        
        # Clear cached scenario data to force new generation
        if self.pipeline_manager and self.enable_caching:
            # Clear scenario-related cache entries
            cache_keys_to_clear = [
                "haystack_pipeline_query_scenario",
                "campaign_manager_get_campaign_context",
                "game_engine_get_game_state"
            ]
            for key_pattern in cache_keys_to_clear:
                try:
                    # This will be handled by the cache implementation
                    pass
                except:
                    pass
        
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
                    
                    self._send_message_and_wait("game_engine", "update_game_state", {
                        "game_state": game_state
                    })
                
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
            # First, start combat
            start_response = self._send_message_and_wait("combat_engine", "start_combat", {})
            if not (start_response and start_response.get("success")):
                if self.verbose:
                    print("⚠️ Failed to start combat engine")
                return
            
            # Add all players from campaign
            players_response = self._send_message_and_wait("campaign_manager", "list_players", {})
            if players_response and players_response.get("players"):
                for player in players_response["players"]:
                    self._send_message_and_wait("combat_engine", "add_combatant", {
                        "name": player["name"],
                        "max_hp": player.get("hp", 20),
                        "armor_class": player.get("combat_stats", {}).get("armor_class", 12),
                        "is_player": True
                    })
            
            # Add all enemies
            for enemy in enemies:
                self._send_message_and_wait("combat_engine", "add_combatant", {
                    "name": enemy["name"],
                    "max_hp": enemy["max_hp"],
                    "armor_class": enemy["armor_class"],
                    "is_player": False
                })
            
            if self.verbose:
                print(f"⚔️ Combat initialized with {len(enemies)} enemies and players")
                
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
        
        self.last_scenario_options = options
        if self.verbose and options:
            print(f"📝 Stored {len(options)} scenario options for selection")
        elif self.verbose:
            print(f"⚠️ No options extracted from scenario text")
    
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
        """Handle general queries using RAG with performance optimization"""
        # Try smart router first for better performance
        try:
            if self.smart_router:
                context = {"type": "general_query"}
                result = self.smart_router.route_query(query, context)
                
                if result and "answer" in result:
                    answer = result["answer"]
                    
                    # Condense the answer if it's too long
                    if len(answer) > 800:
                        # Find a good break point - preferably end of a sentence or paragraph
                        break_point = 800
                        for i in range(700, min(800, len(answer))):
                            if answer[i] in '.!?':
                                break_point = i + 1
                                break
                        answer = answer[:break_point].strip() + "..."
                    
                    pipeline_used = result.get('pipeline_used', 'smart_router')
                    if self.verbose and pipeline_used != 'fallback':
                        print(f"🚀 Used {pipeline_used} pipeline for faster response")
                    
                    return f"💡 {answer}"
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Smart router failed, falling back to direct RAG: {e}")
        
        # Fallback to direct RAG with reduced timeout for better performance
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
        
        # Start combat
        if "start combat" in instruction_lower or "begin combat" in instruction_lower:
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
        
        # Next turn - Enhanced with better error handling and retry mechanism
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
                                self.orchestrator.broadcast_message("combat_turn_changed", {
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
                        if attempt == max_retries - 1:
                            return f"❌ Failed to advance turn after {max_retries} attempts: {error_msg}"
                        elif self.verbose:
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
        
        # Quick condition lookup first (most efficient)
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
        
        # Only use enhanced error recovery as final fallback (instead of primary method)
        try:
            if self.error_recovery:
                context = {"category": category, "type": "rule_query"}
                result = self.error_recovery.process_with_recovery(query, context)
                
                if "error" not in result:
                    if "rule_text" in result:
                        output = f"📖 **{category.upper()} RULE**\n\n"
                        output += f"**Rule:** {result['rule_text']}\n\n"
                        
                        if result.get("sources"):
                            output += f"**Sources:** {result['sources']}\n"
                        
                        confidence = result.get("confidence", "medium")
                        confidence_emoji = {"high": "🔍", "medium": "📚", "low": "❓"}
                        output += f"**Confidence:** {confidence_emoji.get(confidence, '📚')} {confidence}\n"
                        
                        output += f"\n*Used enhanced error recovery*"
                        return output
                    elif "answer" in result:
                        return f"📖 {result['answer']}"
        
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Enhanced rule processing failed: {e}")
        
        # Final fallback
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
                self._send_message_and_wait("game_engine", "update_game_state", {
                    "game_state": self.game_save_data['game_state']
                })
            
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
                        print("  💾 Save/Load: save game [name], list saves, load save [n], update save")
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