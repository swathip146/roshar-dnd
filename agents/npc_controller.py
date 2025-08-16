"""
NPC Controller for DM Assistant
Manages NPC behavior and decision-making using RAG and rule-based systems
Enhanced with direct LLM integration, dialogue generation, and stat management
"""
import random
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from agent_framework import BaseAgent, MessageType, AgentMessage

# Claude LLM integration
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    def component(cls):
        return cls

# Haystack components for RAG integration
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.builders import PromptBuilder
from haystack.components.rankers import SentenceTransformersSimilarityRanker

# Configuration constants
LLM_MODEL = "aws:anthropic.claude-sonnet-4-20250514-v1:0"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_TOP_K = 20
DEFAULT_RANKER_TOP_K = 5

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


@dataclass
class NPCState:
    """Enhanced NPC state management structure"""
    npc_id: str
    name: str
    stats: Dict[str, Any] = None
    status_effects: List[str] = None
    personality: Dict[str, Any] = None
    relationships: Dict[str, Any] = None
    dialogue_state: Dict[str, Any] = None
    memory: List[Dict[str, Any]] = None
    location: str = ""
    current_action: Optional[Dict[str, Any]] = None
    last_updated: float = None
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {}
        if self.status_effects is None:
            self.status_effects = []
        if self.personality is None:
            self.personality = {}
        if self.relationships is None:
            self.relationships = {}
        if self.dialogue_state is None:
            self.dialogue_state = {}
        if self.memory is None:
            self.memory = []
        if self.last_updated is None:
            self.last_updated = time.time()


class NPCControllerAgent(BaseAgent):
    """Enhanced NPC Controller with direct LLM integration, dialogue generation, and stat management"""
    
    def __init__(self, haystack_agent=None, verbose: bool = False):
        super().__init__("npc_controller", "NPCController")
        self.haystack_agent = haystack_agent
        self.verbose = verbose
        
        # Direct LLM integration
        self.has_llm = CLAUDE_AVAILABLE
        self.chat_generator = None
        self.npc_pipeline = None
        
        # NPC state management
        self.npc_states: Dict[str, NPCState] = {}
        self.dialogue_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Initialize LLM and pipeline
        self._setup_llm_integration()
        self._setup_npc_pipeline()
    
    def _setup_handlers(self):
        """Setup enhanced message handlers for NPC controller"""
        # Existing handlers
        self.register_handler("make_decisions", self._handle_make_decisions)
        self.register_handler("decide_for_npc", self._handle_decide_for_npc)
        self.register_handler("get_npc_status", self._handle_get_npc_status)
        
        # New enhanced handlers
        self.register_handler("generate_npc_behavior", self._handle_generate_npc_behavior)
        self.register_handler("generate_npc_dialogue", self._handle_generate_npc_dialogue)
        self.register_handler("update_npc_stats", self._handle_update_npc_stats)
        self.register_handler("get_npc_state", self._handle_get_npc_state)
        self.register_handler("npc_social_interaction", self._handle_npc_social_interaction)
    
    def _setup_llm_integration(self):
        """Initialize direct LLM integration for creative NPC generation"""
        if not self.has_llm:
            if self.verbose:
                print("⚠️ Claude LLM not available, using fallback generation")
            return
        
        try:
            self.chat_generator = AppleGenAIChatGenerator(model=LLM_MODEL)
            if self.verbose:
                print("✅ Claude Sonnet 4 LLM integrated for NPC generation")
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to initialize LLM: {e}")
            self.has_llm = False
    
    def _setup_npc_pipeline(self):
        """Initialize dedicated NPC pipeline with LLM integration"""
        if not self.has_llm:
            return
        
        try:
            # Create NPC-specific pipeline
            self.npc_pipeline = Pipeline()
            
            # Add components for RAG-enhanced NPC behavior
            if self.haystack_agent and hasattr(self.haystack_agent, 'document_store') and self.haystack_agent.document_store:
                # Only add retrieval components if document store is available
                embedder = SentenceTransformersTextEmbedder(model=EMBEDDING_MODEL)
                embedder.warm_up()
                
                from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
                retriever = QdrantEmbeddingRetriever(
                    document_store=self.haystack_agent.document_store,
                    top_k=DEFAULT_TOP_K
                )
                
                ranker = SentenceTransformersSimilarityRanker(
                    model=RANKER_MODEL,
                    top_k=DEFAULT_RANKER_TOP_K
                )
                ranker.warm_up()
                
                self.npc_pipeline.add_component("text_embedder", embedder)
                self.npc_pipeline.add_component("retriever", retriever)
                self.npc_pipeline.add_component("ranker", ranker)
                
                # Connect retrieval components
                self.npc_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
                self.npc_pipeline.connect("retriever.documents", "ranker.documents")
            
            # Add NPC-specific prompt builder and LLM
            prompt_builder = self._create_npc_prompt_builder()
            string_to_chat = StringToChatMessages()
            
            self.npc_pipeline.add_component("prompt_builder", prompt_builder)
            self.npc_pipeline.add_component("string_to_chat", string_to_chat)
            self.npc_pipeline.add_component("chat_generator", self.chat_generator)
            
            # Connect prompt and LLM components
            if "ranker" in self.npc_pipeline.get_component_names():
                self.npc_pipeline.connect("ranker.documents", "prompt_builder.documents")
            self.npc_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
            self.npc_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            
            if self.verbose:
                print("✅ NPC pipeline initialized with RAG and LLM integration")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to initialize NPC pipeline: {e}")
            self.npc_pipeline = None
    
    def _create_npc_prompt_builder(self) -> PromptBuilder:
        """Create NPC-specific prompt builder (moved from HaystackPipelineAgent)"""
        template = """You are an advanced NPC behavior and dialogue specialist. Generate authentic, contextual responses for D&D NPCs with distinct personalities.

{% if documents %}
D&D Context:
{% for document in documents %}
  {{ document.content }}
  ---
{% endfor %}
{% endif %}

NPC Profile:
Name: {{ npc_name }}
Personality: {{ personality }}
Location: {{ location }}
Current State: {{ current_state }}

{% if dialogue_history %}
Recent Conversation:
{% for exchange in dialogue_history %}
  {{ exchange.speaker }}: {{ exchange.content }}
{% endfor %}
{% endif %}

Situation: {{ query }}
{% if game_state %}Game Context: {{ game_state }}{% endif %}

Generate an appropriate response as this NPC. Include:
1. Dialogue (what the NPC says)
2. Action (what the NPC does)
3. Mood (current emotional state)
4. Memory (what to remember about this interaction)

Respond in JSON format:
{
  "dialogue": "NPC's spoken words",
  "action": "NPC's physical action or behavior",
  "mood": "emotional state",
  "memory": "key information to remember"
}"""
        return PromptBuilder(template=template)
    
    def _handle_make_decisions(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle NPC decision-making request"""
        game_state = message.data.get("game_state")
        if not game_state:
            return {"success": False, "error": "No game state provided"}
        
        decisions = self.decide(game_state)
        
        # Send decisions back to game engine for processing
        for decision in decisions:
            self.send_message("game_engine", "enqueue_action", {"action": decision})
        
        return {
            "success": True,
            "decisions_made": len(decisions),
            "decisions": decisions
        }
    
    def _handle_decide_for_npc(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle decision-making for a specific NPC"""
        npc_data = message.data.get("npc")
        game_state = message.data.get("game_state")
        
        if not npc_data or not game_state:
            return {"success": False, "error": "Missing NPC data or game state"}
        
        decision = self._make_npc_decision(npc_data, game_state)
        return {"success": True, "decision": decision}
    
    def _handle_get_npc_status(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle NPC status request"""
        return {
            "has_llm": self.has_llm,
            "pipeline_available": self.npc_pipeline is not None,
            "haystack_available": self.haystack_agent is not None,
            "npc_states_count": len(self.npc_states),
            "agent_type": self.agent_type
        }
    
    def _handle_generate_npc_behavior(self, message: AgentMessage) -> Dict[str, Any]:
        """Generate NPC behavior with context awareness"""
        context = message.data.get("context", "")
        game_state = message.data.get("game_state", {})
        npc_name = message.data.get("npc_name", "Unknown NPC")
        
        try:
            # Ensure NPC state exists
            npc_id = self._get_npc_id(npc_name)
            if npc_id not in self.npc_states:
                self._initialize_npc_state(npc_id, npc_name)
            
            # Generate behavior using LLM pipeline
            behavior_result = self._generate_npc_behavior(npc_id, context, game_state)
            
            if behavior_result:
                return {
                    "success": True,
                    "behavior_description": behavior_result.get("action", "No specific behavior"),
                    "actions": behavior_result.get("action", ""),
                    "reasoning": behavior_result.get("memory", "")
                }
            else:
                # Fallback to rule-based behavior
                npc_data = {"name": npc_name}
                fallback_decision = self._rule_based_decision(npc_data, game_state)
                return {
                    "success": True,
                    "behavior_description": f"Fallback behavior: {fallback_decision.get('type', 'idle') if fallback_decision else 'idle'}",
                    "actions": str(fallback_decision) if fallback_decision else "No action"
                }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to generate NPC behavior: {str(e)}"}
    
    def _handle_generate_npc_dialogue(self, message: AgentMessage) -> Dict[str, Any]:
        """Generate contextual NPC dialogue"""
        npc_name = message.data.get("npc_name", "Unknown NPC")
        player_input = message.data.get("player_input", "")
        context = message.data.get("context", "dialogue")
        
        try:
            # Ensure NPC state exists
            npc_id = self._get_npc_id(npc_name)
            if npc_id not in self.npc_states:
                self._initialize_npc_state(npc_id, npc_name)
            
            # Generate dialogue using LLM
            dialogue_result = self._generate_npc_dialogue(npc_id, context, player_input)
            
            if dialogue_result:
                # Update dialogue history
                if npc_id not in self.dialogue_history:
                    self.dialogue_history[npc_id] = []
                
                self.dialogue_history[npc_id].append({
                    "speaker": "Player",
                    "content": player_input,
                    "timestamp": time.time()
                })
                
                self.dialogue_history[npc_id].append({
                    "speaker": npc_name,
                    "content": dialogue_result.get("dialogue", "..."),
                    "timestamp": time.time()
                })
                
                # Keep only last 10 exchanges
                self.dialogue_history[npc_id] = self.dialogue_history[npc_id][-10:]
                
                # Update NPC memory
                if dialogue_result.get("memory"):
                    self.npc_states[npc_id].memory.append({
                        "type": "dialogue",
                        "content": dialogue_result["memory"],
                        "timestamp": time.time()
                    })
                
                return {
                    "success": True,
                    "dialogue": dialogue_result.get("dialogue", "..."),
                    "mood": dialogue_result.get("mood", "neutral"),
                    "action": dialogue_result.get("action", "")
                }
            else:
                # Fallback dialogue
                return {
                    "success": True,
                    "dialogue": f"*{npc_name} looks at you thoughtfully but says nothing.*",
                    "mood": "neutral",
                    "action": "remains silent"
                }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to generate dialogue: {str(e)}"}
    
    def _handle_update_npc_stats(self, message: AgentMessage) -> Dict[str, Any]:
        """Update NPC stats and status effects"""
        npc_name = message.data.get("npc_name", "")
        stat_updates = message.data.get("stat_updates", {})
        
        if not npc_name:
            return {"success": False, "error": "NPC name required"}
        
        try:
            npc_id = self._get_npc_id(npc_name)
            if npc_id not in self.npc_states:
                self._initialize_npc_state(npc_id, npc_name)
            
            # Update stats
            success = self._update_npc_stats(npc_id, stat_updates)
            
            if success:
                updated_stats = self.npc_states[npc_id].stats
                return {
                    "success": True,
                    "message": f"Updated stats for {npc_name}",
                    "updated_stats": updated_stats,
                    "status_effects": self.npc_states[npc_id].status_effects
                }
            else:
                return {"success": False, "error": "Failed to update NPC stats"}
                
        except Exception as e:
            return {"success": False, "error": f"Error updating stats: {str(e)}"}
    
    def _handle_get_npc_state(self, message: AgentMessage) -> Dict[str, Any]:
        """Retrieve current NPC state information"""
        npc_name = message.data.get("npc_name", "")
        
        if not npc_name:
            return {"success": False, "error": "NPC name required"}
        
        try:
            npc_id = self._get_npc_id(npc_name)
            if npc_id not in self.npc_states:
                return {"success": False, "error": f"NPC {npc_name} not found"}
            
            npc_state = self.npc_states[npc_id]
            return {
                "success": True,
                "npc_state": {
                    "name": npc_state.name,
                    "stats": npc_state.stats,
                    "status_effects": npc_state.status_effects,
                    "personality": npc_state.personality,
                    "location": npc_state.location,
                    "current_action": npc_state.current_action,
                    "last_updated": npc_state.last_updated,
                    "memory_count": len(npc_state.memory)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error retrieving NPC state: {str(e)}"}
    
    def _handle_npc_social_interaction(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle complex social interactions with NPCs"""
        npc_name = message.data.get("npc_name", "")
        interaction_type = message.data.get("interaction_type", "conversation")
        player_action = message.data.get("player_action", "")
        context = message.data.get("context", {})
        
        try:
            npc_id = self._get_npc_id(npc_name)
            if npc_id not in self.npc_states:
                self._initialize_npc_state(npc_id, npc_name)
            
            # Generate social interaction response
            result = self._handle_social_interaction(npc_id, interaction_type, player_action, context)
            
            return {
                "success": True,
                "interaction_result": result,
                "npc_response": result.get("response", ""),
                "relationship_change": result.get("relationship_change", 0),
                "mood_change": result.get("mood_change", "neutral")
            }
            
        except Exception as e:
            return {"success": False, "error": f"Social interaction failed: {str(e)}"}
    
    def decide(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Make decisions for all NPCs in the game state"""
        actions = []
        
        for npc_name, npc in game_state.get("npcs", {}).items():
            # Normalize NPC structure
            npc_obj = npc if isinstance(npc, dict) else {"name": npc}
            npc_obj["name"] = npc_name  # Ensure name is set
            
            decision = self._make_npc_decision(npc_obj, game_state)
            if decision:
                actions.append(decision)
        
        return actions
    
    # Core NPC Generation Methods
    def _generate_npc_behavior(self, npc_id: str, context: str, game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate NPC behavior using LLM pipeline"""
        if not self.npc_pipeline or not self.has_llm:
            return None
        
        try:
            # Gather context from RAG if available
            rag_context = self._gather_npc_context_from_rag(npc_id, context)
            
            # Build enhanced prompt
            npc_state = self.npc_states[npc_id]
            
            # Run NPC pipeline
            result = self._run_npc_pipeline(
                query=context,
                npc_name=npc_state.name,
                personality=npc_state.personality,
                location=npc_state.location,
                current_state=f"HP: {npc_state.stats.get('hp', '?')}, Status: {', '.join(npc_state.status_effects) if npc_state.status_effects else 'Normal'}",
                dialogue_history=self.dialogue_history.get(npc_id, [])[-3:],  # Last 3 exchanges
                game_state=str(game_state)
            )
            
            if result and result.get("success"):
                return self._parse_npc_response(result.get("response", ""))
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ NPC behavior generation failed: {e}")
        
        return None
    
    def _generate_npc_dialogue(self, npc_id: str, context: str, player_input: str = None) -> Optional[Dict[str, Any]]:
        """Generate contextually appropriate NPC dialogue"""
        if not self.has_llm:
            return None
        
        try:
            # Build dialogue context
            dialogue_context = self._build_dialogue_context(npc_id, context)
            
            # Create dialogue-specific prompt
            prompt_data = {
                "query": f"Player says: '{player_input}'. Generate appropriate response." if player_input else context,
                "npc_name": self.npc_states[npc_id].name,
                "personality": dialogue_context.get('npc_personality', {}),
                "location": dialogue_context.get('current_location', ''),
                "current_state": f"Status: {', '.join(self.npc_states[npc_id].status_effects) if self.npc_states[npc_id].status_effects else 'Normal'}",
                "dialogue_history": dialogue_context.get('dialogue_history', []),
                "game_state": ""
            }
            
            # Run pipeline for dialogue generation
            result = self._run_npc_pipeline(**prompt_data)
            
            if result and result.get("success"):
                return self._parse_npc_response(result.get("response", ""))
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ NPC dialogue generation failed: {e}")
        
        return None
    
    def _run_npc_pipeline(self, query: str, npc_name: str, personality: Dict, location: str,
                         current_state: str, dialogue_history: List, game_state: str) -> Dict[str, Any]:
        """Execute NPC pipeline for behavior/dialogue generation"""
        if not self.npc_pipeline:
            return {"success": False, "error": "NPC pipeline not available"}
        
        try:
            # Prepare pipeline inputs
            pipeline_inputs = {
                "prompt_builder": {
                    "query": query,
                    "npc_name": npc_name,
                    "personality": str(personality),
                    "location": location,
                    "current_state": current_state,
                    "dialogue_history": dialogue_history,
                    "game_state": game_state
                }
            }
            
            # Add retrieval inputs if pipeline has retrieval components
            if "text_embedder" in self.npc_pipeline.get_component_names():
                pipeline_inputs.update({
                    "text_embedder": {"text": f"{npc_name} {query}"},
                    "ranker": {"query": f"{npc_name} {query}"}
                })
            
            # Run pipeline
            result = self.npc_pipeline.run(pipeline_inputs)
            
            # Extract response
            if "chat_generator" in result and "replies" in result["chat_generator"]:
                response = result["chat_generator"]["replies"][0].text
                return {"success": True, "response": response}
            else:
                return {"success": False, "error": "No response generated"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # State Management Methods
    def _get_npc_id(self, npc_name: str) -> str:
        """Generate consistent NPC ID from name"""
        return npc_name.lower().replace(" ", "_")
    
    def _initialize_npc_state(self, npc_id: str, npc_name: str):
        """Initialize NPC state with default values"""
        if npc_id not in self.npc_states:
            self.npc_states[npc_id] = NPCState(
                npc_id=npc_id,
                name=npc_name,
                stats={
                    "hp": 15,
                    "max_hp": 15,
                    "ac": 12,
                    "initiative": 10
                },
                personality={
                    "traits": ["curious", "helpful"],
                    "motivation": "assist travelers",
                    "speech_pattern": "friendly and direct"
                }
            )
            
            if self.verbose:
                print(f"📝 Initialized NPC state for {npc_name}")
    
    def _update_npc_stats(self, npc_id: str, stat_updates: Dict[str, Any]) -> bool:
        """Update NPC statistics and handle status effects"""
        if npc_id not in self.npc_states:
            return False
        
        npc = self.npc_states[npc_id]
        
        # Update basic stats
        for stat, value in stat_updates.items():
            if stat in ['hp', 'max_hp', 'ac', 'initiative']:
                npc.stats[stat] = value
            elif stat == 'conditions' or stat == 'status_effects':
                npc.status_effects = value if isinstance(value, list) else [value]
            elif stat == 'location':
                npc.location = value
            elif stat in ['personality', 'traits', 'motivation']:
                if 'personality' not in npc.personality:
                    npc.personality = {}
                npc.personality[stat] = value
        
        # Handle HP changes and unconscious/death conditions
        if 'hp' in stat_updates:
            self._handle_hp_change(npc_id, stat_updates['hp'])
        
        npc.last_updated = time.time()
        
        if self.verbose:
            print(f"📊 Updated stats for {npc.name}: {stat_updates}")
        
        return True
    
    def _handle_hp_change(self, npc_id: str, new_hp: int):
        """Handle NPC HP changes and status effects"""
        npc = self.npc_states[npc_id]
        old_hp = npc.stats.get('hp', 0)
        
        # Add unconscious condition if HP drops to 0
        if new_hp <= 0 and old_hp > 0:
            if 'unconscious' not in npc.status_effects:
                npc.status_effects.append('unconscious')
            npc.memory.append({
                "type": "status_change",
                "content": "Became unconscious",
                "timestamp": time.time()
            })
        elif new_hp > 0 and 'unconscious' in npc.status_effects:
            npc.status_effects.remove('unconscious')
            npc.memory.append({
                "type": "status_change",
                "content": "Regained consciousness",
                "timestamp": time.time()
            })
    
    # RAG Integration Methods
    def _gather_npc_context_from_rag(self, npc_id: str, query_context: str) -> Dict[str, Any]:
        """Query RAG system for relevant NPC background information"""
        if not self.haystack_agent:
            return {}
        
        try:
            npc_name = self.npc_states[npc_id].name
            
            # Build focused query for NPC-specific information
            rag_query = f"NPC {npc_name} background, personality, history, relationships context: {query_context}"
            
            response = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": rag_query,
                "max_docs": 3
            })
            
            if response and response.get("success"):
                return self._process_rag_context(response.get("documents", []))
        except Exception as e:
            if self.verbose:
                print(f"⚠️ RAG context retrieval failed: {e}")
        
        return {}
    
    def _build_dialogue_context(self, npc_id: str, situation: str) -> Dict[str, Any]:
        """Build comprehensive context for dialogue generation"""
        if npc_id not in self.npc_states:
            return {}
        
        npc_state = self.npc_states[npc_id]
        
        context = {
            'npc_personality': npc_state.personality,
            'current_location': npc_state.location,
            'relationship_with_players': npc_state.relationships,
            'recent_events': npc_state.memory[-5:],  # Last 5 memories
            'current_situation': situation,
            'dialogue_history': self.dialogue_history.get(npc_id, [])
        }
        
        return context
    
    def _process_rag_context(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process RAG documents into usable context"""
        context = {
            "background_info": [],
            "personality_traits": [],
            "relationships": [],
            "historical_events": []
        }
        
        for doc in documents:
            content = doc.get("content", "")
            
            # Categorize content based on keywords
            if any(keyword in content.lower() for keyword in ["personality", "trait", "character"]):
                context["personality_traits"].append(content)
            elif any(keyword in content.lower() for keyword in ["relationship", "friend", "enemy", "ally"]):
                context["relationships"].append(content)
            elif any(keyword in content.lower() for keyword in ["history", "past", "event", "happened"]):
                context["historical_events"].append(content)
            else:
                context["background_info"].append(content)
        
        return context
    
    def _parse_npc_response(self, response: str) -> Dict[str, Any]:
        """Parse NPC response from LLM into structured format"""
        try:
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Fallback parsing for non-JSON responses
        result = {
            "dialogue": response,
            "action": "speaks",
            "mood": "neutral",
            "memory": f"Responded: {response[:50]}..."
        }
        
        # Extract quoted dialogue
        import re
        dialogue_match = re.search(r'"([^"]*)"', response)
        if dialogue_match:
            result["dialogue"] = dialogue_match.group(1)
        
        # Extract action descriptions
        action_match = re.search(r'\*([^*]*)\*', response)
        if action_match:
            result["action"] = action_match.group(1)
        
        return result
    
    def _handle_social_interaction(self, npc_id: str, interaction_type: str,
                                 player_action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle complex social interactions with NPCs"""
        npc_state = self.npc_states[npc_id]
        
        # Generate interaction response based on type
        if interaction_type == "persuasion":
            return self._handle_persuasion_attempt(npc_id, player_action, context)
        elif interaction_type == "intimidation":
            return self._handle_intimidation_attempt(npc_id, player_action, context)
        elif interaction_type == "deception":
            return self._handle_deception_attempt(npc_id, player_action, context)
        else:
            # Default conversation
            dialogue_result = self._generate_npc_dialogue(npc_id, f"Social interaction: {player_action}", player_action)
            return {
                "response": dialogue_result.get("dialogue", "...") if dialogue_result else "...",
                "relationship_change": 0,
                "mood_change": "neutral"
            }
    
    def _handle_persuasion_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle persuasion social interaction"""
        # Simplified persuasion logic - could be expanded with skill checks
        success = random.choice([True, False])  # 50/50 for now
        
        if success:
            return {
                "response": f"*{self.npc_states[npc_id].name} seems convinced by your words*",
                "relationship_change": 1,
                "mood_change": "friendly"
            }
        else:
            return {
                "response": f"*{self.npc_states[npc_id].name} remains unconvinced*",
                "relationship_change": 0,
                "mood_change": "skeptical"
            }
    
    def _handle_intimidation_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle intimidation social interaction"""
        success = random.choice([True, False])
        
        if success:
            return {
                "response": f"*{self.npc_states[npc_id].name} backs away nervously*",
                "relationship_change": -1,
                "mood_change": "fearful"
            }
        else:
            return {
                "response": f"*{self.npc_states[npc_id].name} stands their ground defiantly*",
                "relationship_change": -1,
                "mood_change": "hostile"
            }
    
    def _handle_deception_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deception social interaction"""
        success = random.choice([True, False])
        
        if success:
            return {
                "response": f"*{self.npc_states[npc_id].name} believes your story*",
                "relationship_change": 0,
                "mood_change": "trusting"
            }
        else:
            return {
                "response": f"*{self.npc_states[npc_id].name} sees through your deception*",
                "relationship_change": -2,
                "mood_change": "distrustful"
            }
    
    def _make_npc_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a decision for a single NPC"""
        # Check if NPC is marked as simple/rule-based only
        if npc.get("type") == "simple":
            return self._rule_based_decision(npc, game_state)
        
        # Use hybrid approach: try enhanced NPC generation first, fall back to rule-based
        if self.haystack_agent and self.has_llm:
            # Try enhanced NPC behavior generation
            npc_id = self._get_npc_id(npc.get("name", "unknown"))
            if npc_id not in self.npc_states:
                self._initialize_npc_state(npc_id, npc.get("name", "unknown"))
            
            behavior_result = self._generate_npc_behavior(npc_id, "Make a decision", game_state)
            if behavior_result and behavior_result.get("action"):
                # Convert behavior result to decision format
                action_text = behavior_result.get("action", "")
                if "move" in action_text.lower():
                    # Extract destination from action
                    import re
                    dest_match = re.search(r'(?:to|toward)\s+(\w+)', action_text, re.IGNORECASE)
                    if dest_match:
                        return {
                            "actor": npc.get("name"),
                            "type": "move",
                            "args": {"to": dest_match.group(1)}
                        }
                
                return {
                    "actor": npc.get("name"),
                    "type": "raw_event",
                    "args": {"text": f"{npc.get('name')} {action_text}"}
                }
        
        # Fallback to rule-based decision making
        return self._rule_based_decision(npc, game_state)
    
    def _haystack_based_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make NPC decision using Haystack system"""
        prompt = self._build_prompt_for_npc(npc, game_state)
        
        try:
            response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
                "query": prompt,
                "npc_context": str(npc),
                "game_state": str(game_state)
            }, timeout=15.0)
            
            if not response or not response.get("success"):
                return None
            
            result = response.get("result", {})
            answer = result.get("answer", "")
            plan = self._parse_haystack_response(answer)
            
            if isinstance(plan, dict):
                dest = plan.get("move_to") or plan.get("to")
                if dest:
                    return {
                        "actor": npc.get("name"),
                        "type": "move",
                        "args": {"to": dest}
                    }
            elif isinstance(plan, str):
                # Best-effort parse: look for 'to <location>'
                if "to " in plan:
                    to_idx = plan.index("to ")
                    dest = plan[to_idx + 3:].split()[0]
                    return {
                        "actor": npc.get("name"),
                        "type": "move",
                        "args": {"to": dest}
                    }
            
            return None
            
        except Exception:
            return None
    
    def _parse_haystack_response(self, response: str) -> Any:
        """Parse Haystack response to extract actionable information"""
        # Try to parse as JSON first
        import json
        try:
            return json.loads(response)
        except:
            pass
        
        # Return as string for text-based parsing
        return response
    
    def _rule_based_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make NPC decision using rule-based system"""
        # Priority system: flee if HP low, engage players, or patrol
        
        hp = npc.get("hp", 9999)
        max_hp = npc.get("max_hp", hp)
        
        # Flee if HP is critically low
        if max_hp and hp < max(1, max_hp * 0.25):
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": npc.get("flee_to", "safe_spot")}
            }
        
        # Check if player is in same location - engage them
        players = game_state.get("players", {})
        for player_name, player_data in players.items():
            if player_data.get("location") == npc.get("location"):
                return {
                    "actor": npc.get("name"),
                    "type": "raw_event",
                    "args": {"text": f"{npc.get('name')} engages {player_name}."}
                }
        
        # Random patrol behavior
        locations = game_state.get("world", {}).get("locations", [])
        if locations:
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": random.choice(locations)}
            }
        
        return None
    
    def _build_prompt_for_npc(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> str:
        """Build a prompt for RAG-based NPC decision making"""
        prompt_parts = [
            f"NPC: {npc.get('name', 'Unknown')}",
            f"Role: {npc.get('role', 'unknown')}",
            f"HP: {npc.get('hp', '?')}/{npc.get('max_hp', '?')}",
            f"Location: {npc.get('location', '?')}"
        ]
        
        # Add recent events for context
        recent_events = game_state.get('session', {}).get('events', [])[-4:]
        if recent_events:
            prompt_parts.append(f"Recent events: {', '.join(recent_events)}")
        
        # Add player locations for context
        players = game_state.get("players", {})
        if players:
            player_locations = [f"{name}: {data.get('location', '?')}" 
                              for name, data in players.items()]
            prompt_parts.append(f"Player locations: {', '.join(player_locations)}")
        
        prompt_parts.append(
            "What should this NPC do next? Be concise and return a JSON-like answer "
            "with 'move_to' if moving to a location, or describe the action."
        )
        
        return "\n".join(prompt_parts)
    
    def process_tick(self):
        """Process NPC controller tick - mostly reactive, no regular processing needed"""
        pass


# class NPCController:
    """Traditional NPCController class for backward compatibility"""
    
    def __init__(self, haystack_agent: Optional[HaystackPipelineAgent] = None, mode: str = "hybrid"):
        self.haystack_agent = haystack_agent
        self.mode = mode
    
    def decide(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Make decisions for all NPCs"""
        actions = []
        
        for npc_name, npc in game_state.get("npcs", {}).items():
            # Normalize NPC structure
            npc_obj = npc if isinstance(npc, dict) else {"name": npc}
            
            if npc_obj.get("type") == "simple":
                action = self._rule_based(npc_obj, game_state)
                if action:
                    actions.append(action)
            else:
                if self.mode in ("haystack", "hybrid") and self.haystack_agent:
                    prompt = self._build_prompt_for_npc(npc_obj, game_state)
                    try:
                        response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
                            "query": prompt,
                            "npc_context": str(npc_obj),
                            "game_state": str(game_state)
                        }, timeout=15.0)
                        
                        if response and response.get("success"):
                            result = response.get("result", {})
                            answer = result.get("answer", "")
                            
                            # Try to parse the response
                            if "to " in answer:
                                to_idx = answer.index("to ")
                                dest = answer[to_idx + 3:].split()[0]
                                actions.append({
                                    "actor": npc_name,
                                    "type": "move",
                                    "args": {"to": dest}
                                })
                        else:
                            # Fallback to rule-based
                            action = self._rule_based(npc_obj, game_state)
                            if action:
                                actions.append(action)
                    except Exception:
                        # Degrade to rule-based
                        action = self._rule_based(npc_obj, game_state)
                        if action:
                            actions.append(action)
        
        return actions
    
    def _rule_based(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Rule-based NPC decision making"""
        # Example priorities: flee if HP low, attack or patrol
        hp = npc.get("hp", 9999)
        max_hp = npc.get("max_hp", hp)
        
        if max_hp and hp < max(1, max_hp * 0.25):
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": npc.get("flee_to", "safe_spot")}
            }
        
        # If player in same location, choose to approach
        players = game_state.get("players", {})
        for player_name, player_data in players.items():
            if player_data.get("location") == npc.get("location"):
                return {
                    "actor": npc.get("name"),
                    "type": "raw_event",
                    "args": {"text": f"{npc.get('name')} engages {player_name}."}
                }
        
        # Else random patrol
        locations = game_state.get("world", {}).get("locations", [])
        if locations:
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": random.choice(locations)}
            }
        
        return None
    
    def _build_prompt_for_npc(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> str:
        """Build prompt for NPC decision making"""
        parts = [
            f"NPC: {npc.get('name')}",
            f"Role: {npc.get('role', 'unknown')}",
            f"HP: {npc.get('hp', '?')}"
        ]
        parts.append(f"Location: {npc.get('location', '?')}")
        parts.append("Recent events: " + ", ".join(game_state.get('session', {}).get('events', [])[-4:]))
        parts.append("What should this NPC do next? Be concise and return a tiny JSON-like answer with move_to if moving.")
        return "\n".join(parts)