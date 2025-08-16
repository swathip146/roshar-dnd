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

# Haystack components for NPC-specific processing only (no RAG duplication)
from haystack import Pipeline
from haystack.components.builders import PromptBuilder

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
    
    def __init__(self, verbose: bool = False):
        super().__init__("npc_controller", "NPCController")
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
        self.register_handler("game_state_updated", self._handle_game_state_updated)
    
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
        """Initialize simplified NPC pipeline with local LLM only"""
        if not self.has_llm:
            return
        
        try:
            # Create NPC-specific pipeline (NO RAG components)
            self.npc_pipeline = Pipeline()
            
            # Add ONLY NPC-specific prompt builder and LLM
            prompt_builder = self._create_npc_prompt_builder()
            string_to_chat = StringToChatMessages()
            
            self.npc_pipeline.add_component("prompt_builder", prompt_builder)
            self.npc_pipeline.add_component("string_to_chat", string_to_chat)
            self.npc_pipeline.add_component("chat_generator", self.chat_generator)
            
            # Connect ONLY prompt and LLM components (NO retrieval)
            self.npc_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
            self.npc_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            
            if self.verbose:
                print("✅ NPC pipeline initialized with local LLM only")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Failed to initialize NPC pipeline: {e}")
            self.npc_pipeline = None
    
    def _create_npc_prompt_builder(self) -> PromptBuilder:
        """Create NPC-specific prompt builder"""
        template = """You are an advanced NPC behavior and dialogue specialist. Generate authentic, contextual responses for D&D NPCs with distinct personalities.

{% if rag_context %}
Background Context from Knowledge Base:
{{ rag_context }}
---
{% endif %}

{% if behavioral_context %}
Behavioral Guidance:
{{ behavioral_context }}
---
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
        """Generate NPC behavior using local LLM + orchestrator RAG"""
        if not self.npc_pipeline or not self.has_llm:
            return None
        
        try:
            # Step 1: Get RAG context if needed
            rag_context = {}
            behavioral_context = {}
            
            if self._needs_rag_context(context):
                rag_context = self._gather_npc_context_from_rag(npc_id, context)
            
            if self._needs_behavioral_guidance(context):
                behavioral_context = self._get_behavioral_context_from_rag(npc_id, context)
            
            # Step 2: Build enhanced prompt with contexts
            npc_state = self.npc_states[npc_id]
            
            # Step 3: Run local NPC pipeline (LLM only)
            result = self._run_simplified_npc_pipeline(
                query=context,
                npc_name=npc_state.name,
                personality=npc_state.personality,
                location=npc_state.location,
                current_state=f"HP: {npc_state.stats.get('hp', '?')}",
                dialogue_history=self.dialogue_history.get(npc_id, [])[-3:],
                game_state=str(game_state),
                rag_context=rag_context,
                behavioral_context=behavioral_context
            )
            
            if result and result.get("success"):
                return self._parse_npc_response(result.get("response", ""))
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ NPC behavior generation failed: {e}")
        
        return None

    def _needs_rag_context(self, context: str) -> bool:
        """Determine if RAG context retrieval is needed"""
        rag_triggers = ["talk", "conversation", "history", "relationship", "background"]
        return any(trigger in context.lower() for trigger in rag_triggers)

    def _needs_behavioral_guidance(self, context: str) -> bool:
        """Determine if behavioral guidance from RAG is needed"""
        behavior_triggers = ["decision", "choose", "react", "respond", "behavior"]
        return any(trigger in context.lower() for trigger in behavior_triggers)
    
    def _generate_npc_dialogue(self, npc_id: str, context: str, player_input: str = None) -> Optional[Dict[str, Any]]:
        """Generate contextually appropriate NPC dialogue with enhanced RAG integration"""
        if not self.has_llm:
            return None
        
        try:
            # Build comprehensive dialogue context
            dialogue_context = self._build_dialogue_context(npc_id, context)
            
            # Get RAG context for enhanced dialogue
            rag_context = {}
            if player_input and len(player_input) > 5:  # Only for substantial input
                rag_context = self._gather_npc_context_from_rag(npc_id, f"dialogue {player_input}")
            
            # Get rules context for social interactions
            rules_context = {}
            if any(word in (player_input or context).lower() for word in ["persuade", "intimidate", "deceive", "insight"]):
                rules_context = self._get_npc_rules_context("social interaction", f"NPC {self.npc_states[npc_id].name}")
            
            # Create enhanced dialogue prompt
            query_text = f"Player says: '{player_input}'. Generate appropriate response." if player_input else context
            
            result = self._run_simplified_npc_pipeline(
                query=query_text,
                npc_name=self.npc_states[npc_id].name,
                personality=dialogue_context.get('npc_personality', {}),
                location=dialogue_context.get('current_location', ''),
                current_state=f"Status: {', '.join(self.npc_states[npc_id].status_effects) if self.npc_states[npc_id].status_effects else 'Normal'}",
                dialogue_history=dialogue_context.get('dialogue_history', []),
                game_state="",
                rag_context=rag_context,
                behavioral_context=rules_context
            )
            
            if result and result.get("success"):
                return self._parse_npc_response(result.get("response", ""))
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ NPC dialogue generation failed: {e}")
        
        return None
    
    def _run_simplified_npc_pipeline(self, query: str, npc_name: str, personality: Dict,
                                    location: str, current_state: str, dialogue_history: List,
                                    game_state: str, rag_context: Dict = None,
                                    behavioral_context: Dict = None) -> Dict[str, Any]:
        """Execute simplified NPC pipeline for behavior/dialogue generation"""
        if not self.npc_pipeline:
            return {"success": False, "error": "NPC pipeline not available"}
        
        try:
            # Prepare pipeline inputs (NO retrieval components)
            pipeline_inputs = {
                "prompt_builder": {
                    "query": query,
                    "npc_name": npc_name,
                    "personality": str(personality),
                    "location": location,
                    "current_state": current_state,
                    "dialogue_history": dialogue_history,
                    "game_state": game_state,
                    "rag_context": str(rag_context) if rag_context else "",
                    "behavioral_context": str(behavioral_context) if behavioral_context else ""
                }
            }
            
            # Run simplified pipeline (LLM only)
            result = self.npc_pipeline.run(pipeline_inputs)
            
            # Extract response
            if "chat_generator" in result and "replies" in result["chat_generator"]:
                response = result["chat_generator"]["replies"][0].text
                return {"success": True, "response": response}
            else:
                return {"success": False, "error": "No response generated"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_npc_pipeline(self, query: str, npc_name: str, personality: Dict, location: str,
                         current_state: str, dialogue_history: List, game_state: str) -> Dict[str, Any]:
        """Legacy method - redirects to simplified pipeline"""
        return self._run_simplified_npc_pipeline(
            query=query, npc_name=npc_name, personality=personality, location=location,
            current_state=current_state, dialogue_history=dialogue_history, game_state=game_state
        )
    
    # State Management Methods
    def _get_npc_id(self, npc_name: str) -> str:
        """Generate consistent NPC ID from name"""
        return npc_name.lower().replace(" ", "_")
    
    def _initialize_npc_state(self, npc_id: str, npc_name: str):
        """Initialize NPC state with enhanced default values"""
        if npc_id not in self.npc_states:
            self.npc_states[npc_id] = NPCState(
                npc_id=npc_id,
                name=npc_name,
                stats={
                    "hp": 15,
                    "max_hp": 15,
                    "ac": 12,
                    "initiative": 10,
                    "str": 10,
                    "dex": 10,
                    "con": 10,
                    "int": 10,
                    "wis": 10,
                    "cha": 10
                },
                personality={
                    "traits": ["curious", "helpful"],
                    "motivation": "assist travelers",
                    "speech_pattern": "friendly and direct",
                    "combat_traits": [],
                    "relationship_preferences": "neutral"
                },
                relationships={
                    "players": {"general": 0},
                    "reputation": "unknown"
                }
            )
            
            # Add initialization memory
            self.npc_states[npc_id].memory.append({
                "type": "initialization",
                "content": f"NPC {npc_name} initialized in the world",
                "timestamp": time.time()
            })
            
            if self.verbose:
                print(f"📝 Initialized enhanced NPC state for {npc_name}")
    
    def _update_npc_stats(self, npc_id: str, stat_updates: Dict[str, Any]) -> bool:
        """Enhanced NPC statistics management with combat integration"""
        if npc_id not in self.npc_states:
            return False
        
        npc = self.npc_states[npc_id]
        old_stats = npc.stats.copy()
        
        # Update basic stats with validation
        for stat, value in stat_updates.items():
            if stat in ['hp', 'max_hp', 'ac', 'initiative', 'str', 'dex', 'con', 'int', 'wis', 'cha']:
                # Validate stat ranges
                if stat == 'hp':
                    npc.stats[stat] = max(0, min(value, npc.stats.get('max_hp', 100)))
                elif stat in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
                    npc.stats[stat] = max(1, min(30, value))  # D&D stat range
                else:
                    npc.stats[stat] = value
                    
            elif stat == 'conditions' or stat == 'status_effects':
                self._apply_status_effects(npc_id, value if isinstance(value, list) else [value])
            elif stat == 'location':
                old_location = npc.location
                npc.location = value
                if old_location != value:
                    npc.memory.append({
                        "type": "movement",
                        "content": f"Moved from {old_location} to {value}",
                        "timestamp": time.time()
                    })
            elif stat in ['personality', 'traits', 'motivation']:
                if 'personality' not in npc.personality:
                    npc.personality = {}
                npc.personality[stat] = value
            elif stat == 'combat_state':
                npc.current_action = {"type": "combat", "state": value, "timestamp": time.time()}
        
        # Handle HP changes with enhanced logic
        if 'hp' in stat_updates:
            old_hp = old_stats.get('hp', 0)
            self._handle_hp_change(npc_id, stat_updates['hp'], old_hp)
        
        # Handle status effect interactions
        self._process_status_interactions(npc_id)
        
        npc.last_updated = time.time()
        
        if self.verbose:
            changes = {k: v for k, v in stat_updates.items() if old_stats.get(k) != v}
            if changes:
                print(f"📊 Updated stats for {npc.name}: {changes}")
        
        return True

    def _apply_status_effects(self, npc_id: str, effects: List[str]):
        """Apply status effects with proper stacking rules"""
        npc = self.npc_states[npc_id]
        old_effects = npc.status_effects.copy()
        
        # Status effects that don't stack
        exclusive_effects = {
            'conscious': ['unconscious', 'dead'],
            'unconscious': ['conscious', 'dead'],
            'dead': ['conscious', 'unconscious'],
            'calm': ['frightened', 'charmed'],
            'frightened': ['calm'],
            'charmed': ['calm', 'frightened']
        }
        
        for effect in effects:
            if effect not in npc.status_effects:
                # Remove conflicting effects
                if effect in exclusive_effects:
                    for conflicting in exclusive_effects[effect]:
                        if conflicting in npc.status_effects:
                            npc.status_effects.remove(conflicting)
                
                npc.status_effects.append(effect)
                
                # Log status change
                npc.memory.append({
                    "type": "status_change",
                    "content": f"Gained {effect} condition",
                    "timestamp": time.time()
                })
        
        # Remove effects if explicitly set to empty
        if not effects:
            npc.status_effects.clear()

    def _process_status_interactions(self, npc_id: str):
        """Process interactions between different status effects"""
        npc = self.npc_states[npc_id]
        
        # Unconscious NPCs can't take actions
        if 'unconscious' in npc.status_effects:
            npc.current_action = None
            
        # Frightened NPCs have reduced effectiveness
        if 'frightened' in npc.status_effects:
            # Could modify stats temporarily
            pass
            
        # Charmed NPCs might have altered behavior
        if 'charmed' in npc.status_effects:
            # Could influence dialogue generation
            pass
    
    def _handle_hp_change(self, npc_id: str, new_hp: int, old_hp: int = 0):
        """Enhanced HP change handling with death saves and combat states"""
        npc = self.npc_states[npc_id]
        max_hp = npc.stats.get('max_hp', 20)
        
        # Calculate damage/healing amount
        change = new_hp - old_hp
        
        # Handle different HP thresholds
        if new_hp <= 0 and old_hp > 0:
            # Dropping to 0 HP
            if 'unconscious' not in npc.status_effects:
                self._apply_status_effects(npc_id, ['unconscious'])
            
            # Check for massive damage (instant death)
            if abs(change) >= max_hp:
                self._apply_status_effects(npc_id, ['dead'])
                npc.memory.append({
                    "type": "combat_event",
                    "content": f"Died from massive damage ({abs(change)} damage)",
                    "timestamp": time.time()
                })
            else:
                npc.memory.append({
                    "type": "combat_event",
                    "content": f"Dropped to 0 HP (took {abs(change)} damage)",
                    "timestamp": time.time()
                })
                
        elif new_hp > 0 and old_hp <= 0:
            # Recovering from unconsciousness
            if 'unconscious' in npc.status_effects:
                npc.status_effects.remove('unconscious')
            if 'dead' in npc.status_effects:
                npc.status_effects.remove('dead')
                
            npc.memory.append({
                "type": "combat_event",
                "content": f"Regained consciousness (healed {change} HP)",
                "timestamp": time.time()
            })
            
        elif change < 0:
            # Taking damage while conscious
            damage_severity = abs(change) / max_hp
            
            if damage_severity >= 0.5:  # Massive damage
                npc.memory.append({
                    "type": "combat_event",
                    "content": f"Took severe damage ({abs(change)} HP)",
                    "timestamp": time.time()
                })
                # Might trigger fear or desperation
                if random.random() < 0.3:  # 30% chance
                    self._trigger_combat_behavior_change(npc_id, "desperate")
                    
        elif change > 0:
            # Being healed
            npc.memory.append({
                "type": "combat_event",
                "content": f"Healed for {change} HP",
                "timestamp": time.time()
            })

    def _trigger_combat_behavior_change(self, npc_id: str, behavior_type: str):
        """Trigger behavioral changes based on combat events"""
        npc = self.npc_states[npc_id]
        
        if behavior_type == "desperate":
            # Add desperate fighting behavior
            if "desperate" not in npc.personality.get("combat_traits", []):
                if "combat_traits" not in npc.personality:
                    npc.personality["combat_traits"] = []
                npc.personality["combat_traits"].append("desperate")
                
            npc.memory.append({
                "type": "behavior_change",
                "content": "Became desperate in combat",
                "timestamp": time.time()
            })
    
    # RAG Integration Methods
    def _gather_npc_context_from_rag(self, npc_id: str, query_context: str) -> Dict[str, Any]:
        """Query RAG system via orchestrator for NPC background information"""
        try:
            npc_name = self.npc_states[npc_id].name
            
            # Build focused query for NPC-specific information
            rag_query = f"NPC {npc_name} background personality history relationships {query_context}"
            
            # GOOD: Use agent framework messaging
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
    
    def _get_behavioral_context_from_rag(self, npc_id: str, situation: str) -> Dict[str, Any]:
        """Get behavioral guidance via orchestrator"""
        try:
            npc_name = self.npc_states[npc_id].name
            rag_query = f"NPC behavior {npc_name} {situation} actions dialogue personality"
            
            response = self.send_message("haystack_pipeline", "query_rag", {
                "query": rag_query
            })
            
            if response and response.get("success"):
                result = response.get("result", {})
                return {
                    "behavioral_guidance": result.get("answer", ""),
                    "sources": result.get("sources", [])
                }
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Behavioral context retrieval failed: {e}")
        return {}

    def _get_npc_rules_context(self, interaction_type: str, npc_context: str) -> Dict[str, Any]:
        """Get D&D rules context for NPC interactions"""
        try:
            rules_query = f"D&D rules {interaction_type} NPC {npc_context} social interaction skills"
            
            response = self.send_message("haystack_pipeline", "query_rules", {
                "query": rules_query
            })
            
            if response and response.get("success"):
                result = response.get("result", {})
                return {
                    "rules_guidance": result.get("answer", ""),
                    "rule_sources": result.get("sources", [])
                }
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Rules context retrieval failed: {e}")
        return {}
    
    def _build_dialogue_context(self, npc_id: str, situation: str) -> Dict[str, Any]:
        """Build comprehensive context for dialogue generation with enhanced memory"""
        if npc_id not in self.npc_states:
            return {}
        
        npc_state = self.npc_states[npc_id]
        
        # Filter recent dialogue-specific memories
        dialogue_memories = [
            mem for mem in npc_state.memory[-10:]
            if mem.get("type") in ["dialogue", "social_interaction", "relationship_change"]
        ]
        
        context = {
            'npc_personality': npc_state.personality,
            'current_location': npc_state.location,
            'relationship_with_players': npc_state.relationships,
            'recent_events': dialogue_memories,  # Dialogue-relevant memories
            'current_situation': situation,
            'dialogue_history': self.dialogue_history.get(npc_id, [])[-5:]  # Last 5 exchanges
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
        """Handle complex social interactions with NPCs using RAG-enhanced responses"""
        npc_state = self.npc_states[npc_id]
        
        # Get rules context for this type of interaction
        rules_context = self._get_npc_rules_context(interaction_type, f"NPC {npc_state.name} {player_action}")
        
        # Generate interaction response based on type with RAG enhancement
        if interaction_type == "persuasion":
            return self._handle_persuasion_attempt(npc_id, player_action, context, rules_context)
        elif interaction_type == "intimidation":
            return self._handle_intimidation_attempt(npc_id, player_action, context, rules_context)
        elif interaction_type == "deception":
            return self._handle_deception_attempt(npc_id, player_action, context, rules_context)
        else:
            # Enhanced default conversation with context
            dialogue_result = self._generate_npc_dialogue(npc_id, f"Social interaction: {player_action}", player_action)
            
            # Update relationship based on interaction quality
            relationship_change = self._calculate_relationship_change(npc_id, player_action, dialogue_result)
            
            return {
                "response": dialogue_result.get("dialogue", "...") if dialogue_result else "...",
                "relationship_change": relationship_change,
                "mood_change": dialogue_result.get("mood", "neutral") if dialogue_result else "neutral"
            }

    def _calculate_relationship_change(self, npc_id: str, player_action: str, dialogue_result: Dict[str, Any]) -> int:
        """Calculate relationship change based on interaction quality"""
        if not dialogue_result:
            return 0
        
        mood = dialogue_result.get("mood", "neutral")
        action = dialogue_result.get("action", "")
        
        # Positive interactions
        if mood in ["friendly", "happy", "pleased", "amused"]:
            return 1
        elif mood in ["grateful", "impressed", "trusting"]:
            return 2
        # Negative interactions
        elif mood in ["annoyed", "skeptical", "wary"]:
            return -1
        elif mood in ["angry", "hostile", "distrustful", "fearful"]:
            return -2
        
        return 0
    
    def _handle_persuasion_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any],
                                 rules_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle persuasion social interaction with enhanced context"""
        npc_state = self.npc_states[npc_id]
        
        # Enhanced persuasion logic considering personality and rules
        base_chance = 0.5  # 50% base chance
        
        # Modify based on personality
        if "trusting" in npc_state.personality.get("traits", []):
            base_chance += 0.2
        elif "skeptical" in npc_state.personality.get("traits", []):
            base_chance -= 0.2
            
        # Consider relationship history
        relationship_level = npc_state.relationships.get("players", {}).get("general", 0)
        base_chance += relationship_level * 0.1
        
        success = random.random() < base_chance
        
        # Generate contextual response using dialogue system
        dialogue_result = self._generate_npc_dialogue(
            npc_id,
            f"Player attempts persuasion: {player_action}. Success: {success}",
            player_action
        )
        
        if success:
            # Update relationship and memory
            self._update_relationship(npc_id, "players", 1)
            npc_state.memory.append({
                "type": "social_interaction",
                "content": f"Persuaded by player: {player_action}",
                "timestamp": time.time(),
                "success": True
            })
            
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} seems convinced by your words*") if dialogue_result else f"*{npc_state.name} seems convinced by your words*",
                "relationship_change": 1,
                "mood_change": dialogue_result.get("mood", "friendly") if dialogue_result else "friendly"
            }
        else:
            npc_state.memory.append({
                "type": "social_interaction",
                "content": f"Resisted persuasion attempt: {player_action}",
                "timestamp": time.time(),
                "success": False
            })
            
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} remains unconvinced*") if dialogue_result else f"*{npc_state.name} remains unconvinced*",
                "relationship_change": 0,
                "mood_change": dialogue_result.get("mood", "skeptical") if dialogue_result else "skeptical"
            }
    
    def _handle_intimidation_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any],
                                   rules_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle intimidation social interaction with personality consideration"""
        npc_state = self.npc_states[npc_id]
        
        # Enhanced intimidation logic
        base_chance = 0.4  # Lower base chance than persuasion
        
        if "brave" in npc_state.personality.get("traits", []):
            base_chance -= 0.3
        elif "cowardly" in npc_state.personality.get("traits", []):
            base_chance += 0.3
            
        success = random.random() < base_chance
        
        # Always causes relationship damage
        self._update_relationship(npc_id, "players", -1)
        
        dialogue_result = self._generate_npc_dialogue(
            npc_id,
            f"Player attempts intimidation: {player_action}. Success: {success}",
            player_action
        )
        
        npc_state.memory.append({
            "type": "social_interaction",
            "content": f"Intimidation attempt: {player_action}",
            "timestamp": time.time(),
            "success": success
        })
        
        if success:
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} backs away nervously*") if dialogue_result else f"*{npc_state.name} backs away nervously*",
                "relationship_change": -1,
                "mood_change": dialogue_result.get("mood", "fearful") if dialogue_result else "fearful"
            }
        else:
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} stands their ground defiantly*") if dialogue_result else f"*{npc_state.name} stands their ground defiantly*",
                "relationship_change": -1,
                "mood_change": dialogue_result.get("mood", "hostile") if dialogue_result else "hostile"
            }
    
    def _handle_deception_attempt(self, npc_id: str, player_action: str, context: Dict[str, Any],
                                rules_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle deception social interaction with insight consideration"""
        npc_state = self.npc_states[npc_id]
        
        # Enhanced deception logic
        base_chance = 0.5
        
        if "perceptive" in npc_state.personality.get("traits", []):
            base_chance -= 0.2
        elif "gullible" in npc_state.personality.get("traits", []):
            base_chance += 0.2
            
        success = random.random() < base_chance
        
        dialogue_result = self._generate_npc_dialogue(
            npc_id,
            f"Player attempts deception: {player_action}. Success: {success}",
            player_action
        )
        
        npc_state.memory.append({
            "type": "social_interaction",
            "content": f"Deception attempt: {player_action}",
            "timestamp": time.time(),
            "success": success
        })
        
        if success:
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} believes your story*") if dialogue_result else f"*{npc_state.name} believes your story*",
                "relationship_change": 0,
                "mood_change": dialogue_result.get("mood", "trusting") if dialogue_result else "trusting"
            }
        else:
            # Caught lying damages relationship significantly
            self._update_relationship(npc_id, "players", -2)
            return {
                "response": dialogue_result.get("dialogue", f"*{npc_state.name} sees through your deception*") if dialogue_result else f"*{npc_state.name} sees through your deception*",
                "relationship_change": -2,
                "mood_change": dialogue_result.get("mood", "distrustful") if dialogue_result else "distrustful"
            }

    def _update_relationship(self, npc_id: str, target: str, change: int):
        """Update relationship values with tracking"""
        npc_state = self.npc_states[npc_id]
        if "relationships" not in npc_state.relationships:
            npc_state.relationships = {}
        if target not in npc_state.relationships:
            npc_state.relationships[target] = {}
        
        current = npc_state.relationships[target].get("general", 0)
        npc_state.relationships[target]["general"] = max(-10, min(10, current + change))
        
        # Log relationship change
        npc_state.memory.append({
            "type": "relationship_change",
            "content": f"Relationship with {target} changed by {change} (now {npc_state.relationships[target]['general']})",
            "timestamp": time.time()
        })
    
    def _make_npc_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a decision for a single NPC"""
        # Check if NPC is marked as simple/rule-based only
        if npc.get("type") == "simple":
            return self._rule_based_decision(npc, game_state)
        
        # Use hybrid approach: try enhanced NPC generation first, fall back to rule-based
        if self.has_llm:
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
            response = self.send_message("haystack_pipeline", "query_rag", {
                "query": prompt
            })
            
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
    
    def _handle_game_state_updated(self, message: AgentMessage):
        """Handle game_state_updated event - update NPC states based on game changes"""
        # NPCs might care about game state changes (player locations, events, etc.)
        # This handler acknowledges the event and could update NPC states if needed
        game_state = message.data.get("game_state", {})
        timestamp = message.data.get("timestamp", time.time())
        
        # For now, just acknowledge the update
        # Future enhancement: Update NPC states based on game changes
        pass

    def process_tick(self):
        """Enhanced process tick with memory cleanup and state maintenance"""
        current_time = time.time()
        
        # Clean up memories for NPCs that have too many
        for npc_id, npc_state in self.npc_states.items():
            if len(npc_state.memory) > 50:
                self._cleanup_old_memories(npc_id)
            
            # Update last_updated if NPC hasn't been active
            if current_time - npc_state.last_updated > 3600:  # 1 hour
                npc_state.last_updated = current_time

    def _cleanup_old_memories(self, npc_id: str):
        """Clean up old memories for an NPC"""
        if npc_id in self.npc_states:
            # Keep only the most recent 30 memories
            self.npc_states[npc_id].memory = self.npc_states[npc_id].memory[-30:]


# Deprecated NPCController class removed - use NPCControllerAgent instead