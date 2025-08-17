"""
Fixed Haystack Native DM Orchestrator
Pure Haystack-based orchestration for D&D Assistant - No circular dependencies
"""

import os
import time
from typing import Dict, Any, List, Optional
from haystack import Pipeline, component
from haystack.components.builders import PromptBuilder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore

# Import pure event sourcing components (no circular dependencies)
from core.pure_event_sourcing import GameEvent, EventStore, StateProjector

# Configuration constants from haystack_pipeline_agent
DEFAULT_EMBEDDING_DIM = 384
LLM_MODEL = "aws:anthropic.claude-sonnet-4-20250514-v1:0"

# Claude-specific imports
try:
    from hwtgenielib import component as hwtgenie_component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    def hwtgenie_component(cls):
        return cls

# Suppress warnings
import warnings
warnings.filterwarnings("ignore")


@component
class StringToChatMessages:
    """Converts a string prompt into a list of ChatMessage objects."""
    
    @component.output_types(messages=list[ChatMessage] if CLAUDE_AVAILABLE else list)
    def run(self, prompt: str):
        """Run the component."""
        if CLAUDE_AVAILABLE:
            return {"messages": [ChatMessage.from_user(prompt)]}
        else:
            return {"messages": [{"role": "user", "content": prompt}]}


class SimpleNativePipelineRegistry:
    """Simple pipeline registry without external dependencies"""
    
    def __init__(self):
        self.pipelines: Dict[str, Pipeline] = {}
        
    def register_pipeline(self, intent: str, pipeline: Pipeline) -> bool:
        """Register a pipeline for an intent"""
        self.pipelines[intent] = pipeline
        return True
        
    def get_pipeline(self, intent: str) -> Optional[Pipeline]:
        """Get pipeline for intent"""
        return self.pipelines.get(intent)
        
    def get_registered_intents(self) -> List[str]:
        """Get list of registered intents"""
        return list(self.pipelines.keys())


class HaystackDMOrchestrator:
    """Pure Haystack-based orchestration for D&D Assistant"""
    
    def __init__(self,
                 document_store: Optional[QdrantDocumentStore] = None,
                 campaigns_dir: str = "resources/current_campaign",
                 collection_name: str = "dnd_documents",
                 verbose: bool = False):
        self.verbose = verbose
        self.campaigns_dir = campaigns_dir
        self.collection_name = collection_name
        self.has_llm = CLAUDE_AVAILABLE
        
        # Initialize core Haystack components
        self.document_store = document_store or self._setup_document_store()
        self.pipeline_registry = SimpleNativePipelineRegistry()
        
        # Initialize LLM for intent classification and generation
        if CLAUDE_AVAILABLE:
            self.llm = AppleGenAIChatGenerator(model=LLM_MODEL)
            if verbose:
                print("✓ Using Claude Sonnet 4 for LLM operations")
        else:
            self.llm = MockClaudeGenerator()
            if verbose:
                print("⚠️ Claude not available, using mock generator")
        
        # Initialize intent classification pipeline
        self.intent_pipeline = self._create_intent_classification_pipeline()
        
        # Initialize game state manager
        self.game_state = GameStateManager(verbose=verbose)
        
        if verbose:
            print("🚀 HaystackDMOrchestrator initialized")
    
    def _setup_document_store(self) -> Optional[QdrantDocumentStore]:
        """Setup Qdrant document store with local storage"""
        try:
            # Initialize local document store
            document_store = QdrantDocumentStore(
                path="../qdrant_storage",
                index=self.collection_name,
                embedding_dim=DEFAULT_EMBEDDING_DIM
            )
            
            if self.verbose:
                print(f"✓ Connected to local Qdrant storage: {self.collection_name}")
            return document_store
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Local Qdrant storage not available, running in offline mode: {e}")
            # Don't raise error, just disable document store for graceful degradation
            return None
    
    def _create_intent_classification_pipeline(self) -> Pipeline:
        """Create intent classification pipeline using LLM"""
        
        # Create intent classification component
        intent_classifier = IntentClassificationComponent(self.llm)
        
        # Create pipeline
        pipeline = Pipeline()
        pipeline.add_component("intent_classifier", intent_classifier)
        
        return pipeline
    
    def classify_intent(self, command: str, context: Dict[str, Any] = None) -> str:
        """Classify user command into intent"""
        try:
            result = self.intent_pipeline.run({
                "query": command,
                "context": context or {}
            })
            
            return result.get("intent_classifier", {}).get("intent", "UNKNOWN")
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Intent classification failed: {e}")
            return "UNKNOWN"
    
    def process_command(self, command: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process command through appropriate Haystack pipeline"""
        
        # Classify intent
        intent = self.classify_intent(command, context)
        
        if self.verbose:
            print(f"🎯 Classified intent: {intent}")
        
        # Get appropriate pipeline for intent
        try:
            pipeline = self.pipeline_registry.get_pipeline(intent)
            if not pipeline:
                return {
                    "success": False,
                    "error": f"No pipeline found for intent: {intent}",
                    "intent": intent
                }
            
            # Execute pipeline
            result = pipeline.run({
                "query": command,
                "context": context or {},
                "intent": intent
            })
            
            # Add metadata
            result["intent"] = intent
            result["timestamp"] = time.time()
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Pipeline execution failed: {e}")
            
            return {
                "success": False,
                "error": f"Pipeline execution failed: {str(e)}",
                "intent": intent
            }
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about registered pipelines"""
        return {
            "registered_intents": self.pipeline_registry.get_registered_intents(),
            "total_pipelines": len(self.pipeline_registry.pipelines),
            "game_state_active": self.game_state is not None,
            "document_store_count": len(self.document_store.filter_documents()) if self.document_store else 0
        }
    
    def register_pipeline(self, intent: str, pipeline: Pipeline) -> bool:
        """Register a new pipeline for an intent"""
        return self.pipeline_registry.register_pipeline(intent, pipeline)
    
    def get_game_state(self) -> Dict[str, Any]:
        """Get current game state"""
        return self.game_state.get_current_state()
    
    def update_game_state(self, update_data: Dict[str, Any]) -> bool:
        """Update game state"""
        return self.game_state.apply_state_update(update_data)


@component
class IntentClassificationComponent:
    """Classify user commands into intents using LLM"""
    
    def __init__(self, llm_generator):
        self.llm = llm_generator
        self.has_llm = CLAUDE_AVAILABLE
        
        # Define supported intents
        self.intents = [
            "SKILL_CHECK", "SCENARIO_CHOICE", "RULE_QUERY",
            "COMBAT_ACTION", "LORE_LOOKUP", "CHARACTER_MANAGEMENT",
            "INVENTORY_ACTION", "SPELL_CASTING", "SESSION_MANAGEMENT",
            "CAMPAIGN_MANAGEMENT", "NPC_INTERACTION", "DICE_ROLL"
        ]
        
        # Create prompt builder for intent classification
        self.prompt_builder = PromptBuilder(
            template=self._get_intent_prompt_template(),
            required_variables=["query", "context"]
        )
        
        # Create string to chat converter for Claude
        if self.has_llm:
            self.string_to_chat = StringToChatMessages()
    
    def _get_intent_prompt_template(self) -> str:
        """Get the prompt template for intent classification"""
        return """
You are a D&D Assistant that classifies user commands into specific intents.

Available Intents:
- SKILL_CHECK: Making skill checks, ability checks, saving throws
- SCENARIO_CHOICE: Choosing actions in scenarios, making decisions
- RULE_QUERY: Looking up D&D rules, mechanics, clarifications  
- COMBAT_ACTION: Combat actions, attacks, spells in combat
- LORE_LOOKUP: Looking up lore, world information, campaign details
- CHARACTER_MANAGEMENT: Managing character stats, leveling, equipment
- INVENTORY_ACTION: Managing inventory, items, equipment
- SPELL_CASTING: Casting spells outside of combat
- SESSION_MANAGEMENT: Starting/ending sessions, saving game state
- CAMPAIGN_MANAGEMENT: Managing campaigns, settings, world state
- NPC_INTERACTION: Talking to NPCs, social interactions
- DICE_ROLL: Simple dice rolling without specific context

User Command: {{query}}

Context: {{context}}

Classify this command into ONE of the available intents. Respond with only the intent name.

Intent:"""
    
    @component.output_types(intent=str, confidence=float, reasoning=str)
    def run(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Classify the user query into an intent"""
        
        try:
            # Build prompt
            prompt_result = self.prompt_builder.run(
                query=query,
                context=str(context or {})
            )
            
            if self.has_llm:
                # Convert to chat messages for Claude
                chat_result = self.string_to_chat.run(prompt_result["prompt"])
                
                # Generate classification using Claude
                llm_result = self.llm.run(messages=chat_result["messages"])
                
                # Extract intent from response
                response = llm_result.get("replies", [{}])[0].get("content", "").strip().upper()
            else:
                # Use mock generator
                llm_result = self.llm.run(prompt=prompt_result["prompt"])
                response = llm_result.get("replies", [""])[0].strip().upper()
            
            # Validate intent
            if response in self.intents:
                intent = response
                confidence = 0.9  # High confidence if exact match
            else:
                # Try fuzzy matching or default
                intent = self._fuzzy_match_intent(response, query)
                confidence = 0.6  # Lower confidence for fuzzy match
            
            reasoning = f"LLM Response: {response}, Matched: {intent}"
            
            return {
                "intent": intent,
                "confidence": confidence,
                "reasoning": reasoning
            }
            
        except Exception as e:
            # Fallback to heuristic classification
            intent = self._heuristic_classification(query)
            
            return {
                "intent": intent,
                "confidence": 0.3,  # Low confidence for fallback
                "reasoning": f"Fallback classification due to error: {str(e)}"
            }
    
    def _fuzzy_match_intent(self, response: str, query: str) -> str:
        """Try to fuzzy match the LLM response to a valid intent"""
        
        # Check if response contains any intent keywords
        for intent in self.intents:
            if intent.lower() in response.lower():
                return intent
        
        # Fallback to heuristic classification
        return self._heuristic_classification(query)
    
    def _heuristic_classification(self, query: str) -> str:
        """Fallback heuristic classification based on keywords"""
        
        query_lower = query.lower()
        
        # Skill check keywords
        skill_keywords = ["roll", "check", "d20", "athletics", "perception", "stealth", "persuasion"]
        if any(keyword in query_lower for keyword in skill_keywords):
            return "SKILL_CHECK"
        
        # Combat keywords
        combat_keywords = ["attack", "damage", "hit", "ac", "initiative", "combat"]
        if any(keyword in query_lower for keyword in combat_keywords):
            return "COMBAT_ACTION"
        
        # Rule query keywords
        rule_keywords = ["rule", "how", "what", "explain", "mechanic"]
        if any(keyword in query_lower for keyword in rule_keywords):
            return "RULE_QUERY"
        
        # Character management keywords
        character_keywords = ["level", "character", "stats", "hp", "xp"]
        if any(keyword in query_lower for keyword in character_keywords):
            return "CHARACTER_MANAGEMENT"
        
        # Default to rule query for unknown commands
        return "RULE_QUERY"


class GameStateManager:
    """Centralized game state management using event sourcing"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.current_state = {
            "characters": {},
            "campaign": {},
            "session": {
                "active": False,
                "start_time": None,
                "session_id": None
            },
            "combat": {
                "active": False,
                "turn_order": [],
                "current_turn": 0
            },
            "world_state": {},
            "events": []
        }
        
        # Event sourcing components
        self.event_store = EventStore()
        self.state_projector = StateProjector()
        
        if verbose:
            print("🎮 GameStateManager initialized with event sourcing")
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current projected game state"""
        # Project current state from events
        if self.event_store.events:
            return self.state_projector.project_state(self.event_store.events)
        return self.current_state.copy()
    
    def apply_state_update(self, update_data: Dict[str, Any]) -> bool:
        """Apply state update through event sourcing"""
        try:
            # Create event for state update
            event = GameEvent(
                event_id=f"state_update_{int(time.time() * 1000)}",
                event_type="game_state.updated",
                actor="game_state_manager",
                payload=update_data
            )
            
            # Append event to store
            self.event_store.append_event(event)
            
            # Update current state cache
            self.current_state.update(update_data)
            
            if self.verbose:
                print(f"📊 Game state updated: {list(update_data.keys())}")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to update game state: {e}")
            return False
    
    def get_active_characters(self) -> List[Dict[str, Any]]:
        """Get list of active characters"""
        return list(self.current_state.get("characters", {}).values())
    
    def get_campaign_context(self) -> Dict[str, Any]:
        """Get current campaign context"""
        return self.current_state.get("campaign", {})
    
    def get_session_state(self) -> Dict[str, Any]:
        """Get current session state"""
        return self.current_state.get("session", {})
    
    def get_session_id(self) -> Optional[str]:
        """Get current session ID"""
        return self.current_state.get("session", {}).get("session_id")


class MockClaudeGenerator:
    """Mock Claude generator for testing without Claude available"""
    
    def run(self, prompt: str = None, messages: List = None) -> Dict[str, Any]:
        """Mock LLM response based on prompt content"""
        
        # Extract content from either prompt or messages
        if messages and len(messages) > 0:
            if isinstance(messages[0], dict):
                content = messages[0].get("content", "").lower()
            else:
                content = str(messages[0]).lower()
        elif prompt:
            content = prompt.lower()
        else:
            content = ""
        
        # Simple heuristic classification
        if "roll" in content or "check" in content:
            intent = "SKILL_CHECK"
        elif "attack" in content or "combat" in content:
            intent = "COMBAT_ACTION"
        elif "rule" in content or "how" in content:
            intent = "RULE_QUERY"
        elif "lore" in content or "world" in content:
            intent = "LORE_LOOKUP"
        else:
            intent = "RULE_QUERY"
        
        return {
            "replies": [{"content": intent}] if messages else [intent]
        }