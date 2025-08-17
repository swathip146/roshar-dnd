"""
Scenario Generator for DM Assistant
Generates dynamic scenarios and handles player choices using RAG-first approach with orchestrator communication
"""
import json
import random
import re
import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from agent_framework import BaseAgent, MessageType, AgentMessage

# Claude-specific imports
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    def component(cls):
        return cls


# Configuration constants
LLM_MODEL = "aws:anthropic.claude-sonnet-4-20250514-v1:0"
RAG_REQUEST_TIMEOUT = 10.0  # seconds - reduced from 30s for better UX
MAX_RAG_DOCUMENTS = 3
CIRCUIT_BREAKER_THRESHOLD = 5  # failures before opening circuit
CIRCUIT_BREAKER_RESET_TIME = 60  # seconds
BACKOFF_BASE_DELAY = 1.0  # seconds

@dataclass
class PendingScenarioRequest:
    """Tracks a scenario request waiting for RAG completion"""
    original_message_id: str
    original_message: AgentMessage
    rag_request_id: str
    timestamp: float
    context: Dict[str, Any]
    timeout: float


class ScenarioGeneratorAgent(BaseAgent):
    """
    Scenario Generator Agent with RAG-first architecture
    
    This agent generates dynamic D&D scenarios by:
    1. First attempting to retrieve relevant documents via RAG
    2. Using RAG context to enhance scenario generation when available
    3. Falling back to creative generation when RAG is unavailable
    4. All communication goes through the orchestrator message bus
    """
    
    def __init__(self, verbose: bool = False):
        super().__init__("scenario_generator", "ScenarioGenerator")
        self.verbose = verbose
        self.has_llm = CLAUDE_AVAILABLE
        
        # Track RAG utilization for monitoring
        self.rag_requests_made = 0
        self.rag_successes = 0
        self.rag_failures = 0
        
        # Threading-adapted state tracking (replaces complex pending_rag_requests)
        self.pending_scenarios: Dict[str, PendingScenarioRequest] = {}
        self.request_lock = threading.RLock()  # Reentrant lock for nested acquisitions
        
        # Circuit breaker per agent (granular failure tracking)
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.circuit_breaker_open_until: Dict[str, float] = defaultdict(float)
        
        # Initialize LLM for creative generation
        if self.has_llm:
            try:
                self.chat_generator = AppleGenAIChatGenerator(
                    model=LLM_MODEL
                )
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to initialize LLM: {e}")
                self.chat_generator = None
                self.has_llm = False
        else:
            self.chat_generator = None
    
    def _setup_handlers(self):
        """Setup message handlers for scenario generator"""
        self.register_handler("generate_scenario", self._handle_generate_scenario)
        self.register_handler("apply_player_choice", self._handle_apply_player_choice)
        self.register_handler("get_generator_status", self._handle_get_generator_status)
        self.register_handler("game_state_updated", self._handle_game_state_updated)
        self.register_handler("campaign_selected", self._handle_campaign_selected)
        
        # Handler for receiving RAG document responses
        self.register_handler("retrieve_documents", self._handle_retrieve_documents_response)
    
    def _handle_retrieve_documents_response(self, message: AgentMessage):
        """Handle response from haystack pipeline with retrieved documents"""
        if not self._validate_message_data(message):
            return
        
        # Extract response data
        response_to = message.response_to
        if not response_to:
            if self.verbose:
                print(f"⚠️ ScenarioGenerator: Received retrieve_documents response without response_to field")
            return
        
        with self.request_lock:
            # Find the matching pending scenario request
            req = self.pending_scenarios.get(response_to)
            
            # CRITICAL FIX: Late response disposal
            if not req or time.time() > req.timestamp + req.timeout:
                if self.verbose:
                    print(f"🗑️ ScenarioGenerator: Dropping expired/unknown response for {response_to[:8]}")
                return  # Late response ignored - fixes "unknown request" errors
            
            try:
                # Extract documents from response
                if message.data.get("success", False):
                    documents = message.data.get("documents", [])
                    
                    if self.verbose:
                        print(f"✅ ScenarioGenerator: Received {len(documents)} RAG documents for request {response_to[:8]}")
                    
                    # Complete scenario generation with RAG data
                    self._complete_scenario_with_rag(req, documents)
                    self.rag_successes += 1
                    
                    # Reset circuit breaker for haystack_pipeline
                    self.failure_counts["haystack_pipeline"] = 0
                    
                else:
                    error = message.data.get("error", "Unknown error")
                    
                    if self.verbose:
                        print(f"❌ ScenarioGenerator: RAG request failed: {error}")
                    
                    # Complete scenario generation with fallback (no RAG)
                    self._complete_scenario_with_fallback(req)
                    self.rag_failures += 1
                    
                    # Track circuit breaker failure
                    self._record_circuit_breaker_failure("haystack_pipeline")
                
                # Clean up completed request
                del self.pending_scenarios[response_to]
                
            except Exception as e:
                if self.verbose:
                    print(f"❌ ScenarioGenerator: Error processing RAG response: {e}")
                
                # Fallback on error
                self._complete_scenario_with_fallback(req)
                del self.pending_scenarios[response_to]
    
    def _should_use_rag(self) -> bool:
        """Check if RAG should be used based on circuit breaker state"""
        current_time = time.time()
        
        # Check if circuit breaker is open for haystack_pipeline
        if current_time < self.circuit_breaker_open_until.get("haystack_pipeline", 0):
            if self.verbose:
                print(f"🚫 ScenarioGenerator: Circuit breaker open for haystack_pipeline, using fallback")
            return False
        
        return True
    
    def _record_circuit_breaker_failure(self, agent_name: str):
        """Record a failure and potentially open the circuit breaker"""
        self.failure_counts[agent_name] += 1
        
        if self.failure_counts[agent_name] >= CIRCUIT_BREAKER_THRESHOLD:
            # Open circuit breaker
            self.circuit_breaker_open_until[agent_name] = time.time() + CIRCUIT_BREAKER_RESET_TIME
            if self.verbose:
                print(f"🔌 ScenarioGenerator: Circuit breaker opened for {agent_name} (failures: {self.failure_counts[agent_name]})")
    
    def _start_rag_enhanced_generation(self, message: AgentMessage, query: str, campaign_context: str, game_state: str):
        """Start async RAG-enhanced scenario generation without blocking"""
        if self.verbose:
            print(f"🚀 ScenarioGenerator: Starting async RAG generation for query: '{query[:50]}...'")
        
        self.rag_requests_made += 1
        
        try:
            # Send RAG request to haystack pipeline
            rag_message_id = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": query,
                "max_docs": MAX_RAG_DOCUMENTS
            })
            
            # Store pending scenario request for completion by callback
            with self.request_lock:
                self.pending_scenarios[rag_message_id] = PendingScenarioRequest(
                    original_message_id=message.id,
                    original_message=message,
                    rag_request_id=rag_message_id,
                    timestamp=time.time(),
                    context={
                        "query": query,
                        "campaign_context": campaign_context,
                        "game_state": game_state
                    },
                    timeout=RAG_REQUEST_TIMEOUT
                )
            
            if self.verbose:
                print(f"📝 ScenarioGenerator: Stored pending request {rag_message_id[:8]} for async completion")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error starting RAG generation: {e}")
            
            # Fallback to immediate generation and send response
            scenario = self._generate_creative_scenario(query, [], campaign_context, game_state)
            self.send_response(message, {
                "success": True,
                "scenario": scenario,
                "used_rag": False,
                "source_count": 0
            })
    
    def _complete_scenario_with_rag(self, req: PendingScenarioRequest, documents: List[Dict[str, Any]]):
        """Complete scenario generation with RAG documents"""
        try:
            context = req.context
            scenario = self._generate_rag_enhanced_scenario(
                context["query"],
                documents,
                {"story_arc": context["campaign_context"], "query": context["query"]}
            )
            
            if self.verbose:
                print(f"✅ ScenarioGenerator: Completed RAG-enhanced scenario with {len(documents)} documents")
            
            # Send final response to original requester
            self.send_response(req.original_message, {
                "success": True,
                "scenario": scenario,
                "used_rag": True,
                "source_count": len(documents)
            })
            
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error completing RAG scenario: {e}")
            self._complete_scenario_with_fallback(req)
    
    def _complete_scenario_with_fallback(self, req: PendingScenarioRequest):
        """Complete scenario generation with fallback (no RAG)"""
        try:
            context = req.context
            scenario = self._generate_creative_scenario(
                context["query"],
                [],
                context["campaign_context"],
                context["game_state"]
            )
            
            if self.verbose:
                print(f"🎨 ScenarioGenerator: Completed fallback scenario generation")
            
            # Send final response to original requester
            self.send_response(req.original_message, {
                "success": True,
                "scenario": scenario,
                "used_rag": False,
                "source_count": 0
            })
            
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error in fallback generation: {e}")
            
            # Final fallback - send error response
            self.send_response(req.original_message, {
                "success": False,
                "error": f"Scenario generation failed: {str(e)}"
            })
        
    def _cleanup_expired_requests(self):
        """Clean up expired scenario requests to prevent memory leaks"""
        current_time = time.time()
        expired_requests = []
        
        with self.request_lock:
            for message_id, req in self.pending_scenarios.items():
                if current_time - req.timestamp > req.timeout * 2:
                    expired_requests.append(message_id)
            
            for message_id in expired_requests:
                if self.verbose:
                    print(f"🧹 ScenarioGenerator: Cleaning up expired scenario request {message_id[:8]}")
                
                # Send timeout error response if possible
                req = self.pending_scenarios[message_id]
                try:
                    self.send_response(req.original_message, {
                        "success": False,
                        "error": "Request timed out",
                        "used_rag": False,
                        "source_count": 0
                    })
                except Exception:
                    pass  # Best effort cleanup
                
                del self.pending_scenarios[message_id]
    
    def _retry_with_backoff(self, func, max_retries: int = 2):
        """Execute function with exponential backoff on failure (threading version)"""
        delay = BACKOFF_BASE_DELAY
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except Exception as e:
                if attempt >= max_retries:
                    raise e
                
                # Add jitter to prevent thundering herd
                jittered_delay = delay + random.uniform(0, 0.5)
                if self.verbose:
                    print(f"🔄 ScenarioGenerator: Retry {attempt + 1}/{max_retries} after {jittered_delay:.1f}s")
                
                time.sleep(jittered_delay)
                delay *= 2
        
        raise RuntimeError("Max retries exceeded")
    
    def _generate_rag_enhanced_scenario(self, query: str, documents: List[Dict[str, Any]], seed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate scenario enhanced with RAG context
        
        Args:
            query: Original query/prompt
            documents: Retrieved RAG documents
            seed: Scenario seed information
            
        Returns:
            Generated scenario dictionary
        """
        if self.verbose:
            print(f"📚 ScenarioGenerator: Generating RAG-enhanced scenario with {len(documents)} documents")
        
        # Build context-aware prompt
        prompt = self._build_rag_enhanced_prompt(query, documents, seed)
        
        # Generate with LLM if available
        if self.has_llm and self.chat_generator:
            try:
                scenario = self._generate_with_llm(prompt)
                if scenario:
                    scenario["generation_method"] = "rag_enhanced_llm"
                    scenario["rag_documents_used"] = len(documents)
                    self.rag_successes += 1
                    return scenario
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ ScenarioGenerator: LLM generation failed, using fallback: {e}")
        
        # Fallback to creative generation
        return self._generate_creative_scenario(query, documents, seed.get('story_arc', ''), str(seed))
    
    def _handle_generate_scenario(self, message: AgentMessage):
        """Handle scenario generation request with RAG-first approach"""
        # Validate input data
        if not self._validate_message_data(message):
            return {"success": False, "error": "Invalid message data format"}
        
        game_state = message.data.get("game_state")
        query = message.data.get("query", "")
        campaign_context = message.data.get("campaign_context", "")
        use_rag = message.data.get("use_rag", True)
        
        if not game_state:
            return {"success": False, "error": "No game state provided"}
        
        try:
            if self.verbose:
                print(f"🎭 ScenarioGenerator: Processing scenario request (use_rag: {use_rag})")
            
            # CRITICAL FIX: Consistent handler response pattern
            if query and use_rag and self._should_use_rag():
                # Start async RAG-enhanced generation - don't send response yet
                self._start_rag_enhanced_generation(message, query, campaign_context, str(game_state))
                return None  # Framework won't send response - callback will complete it
                
            elif query:
                # Direct query generation without RAG
                scenario = self._generate_creative_scenario(query, [], campaign_context, str(game_state))
                
                return {
                    "success": True,
                    "scenario": scenario,
                    "used_rag": False,
                    "source_count": 0
                }
            else:
                # Traditional state-based generation
                scene_json, options_text = self.generate(game_state)
                
                # Send the generated scenario back to game engine
                self.send_message("game_engine", "add_scene_to_history", {
                    "scene_data": scene_json,
                    "options_text": options_text
                })
                
                return {
                    "success": True,
                    "scene_json": scene_json,
                    "options_text": options_text
                }
                
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error in scenario generation: {e}")
            return {"success": False, "error": str(e)}
    
    def _handle_apply_player_choice(self, message: AgentMessage):
        """Handle player choice application with RAG-first approach"""
        if not self._validate_message_data(message):
            self.send_response(message, {"success": False, "error": "Invalid message data format"})
            return None  # Indicate response was sent directly
        
        game_state = message.data.get("game_state")
        player = message.data.get("player")
        choice = message.data.get("choice")
        
        if not all([game_state, player, choice]):
            self.send_response(message, {"success": False, "error": "Missing game state, player, or choice"})
            return None  # Indicate response was sent directly
        
        try:
            if self.verbose:
                print(f"⚡ ScenarioGenerator: Processing player choice for {player}")
            
            continuation = self.apply_player_choice(game_state, player, choice)
            self.send_response(message, {"success": True, "continuation": continuation})
            return None  # Indicate response was sent directly
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error applying player choice: {e}")
            self.send_response(message, {"success": False, "error": str(e)})
            return None  # Indicate response was sent directly
    
    def _handle_get_generator_status(self, message: AgentMessage):
        """Handle generator status request with RAG metrics"""
        self.send_response(message, {
            "llm_available": self.has_llm,
            "chat_generator_available": self.chat_generator is not None,
            "verbose": self.verbose,
            "agent_type": self.agent_type,
            "uses_orchestrator_communication": True,
            "rag_metrics": {
                "requests_made": self.rag_requests_made,
                "successes": self.rag_successes,
                "failures": self.rag_failures,
                "success_rate": (self.rag_successes / max(1, self.rag_requests_made)) * 100
            }
        })
    
    # OLD BLOCKING METHOD REMOVED - replaced with async _start_rag_enhanced_generation
    
    def _format_scenario_response(self, scenario: Dict[str, Any], seed: Dict[str, Any]) -> Tuple[str, str]:
        """
        Format scenario response consistently
        
        Args:
            scenario: Generated scenario dictionary
            seed: Scenario seed information
            
        Returns:
            Tuple of (scene_json, options_text)
        """
        # Extract scenario components
        scene_text = scenario.get("scenario_text", f"You are at {seed.get('location', 'unknown')}. Recent events: {', '.join(seed.get('recent', []))}.")
        options = scenario.get("options", [])
        
        # Generate fallback options if needed
        if not options:
            options = [
                "1. **Investigation Check (DC 15)** - Examine the area carefully",
                "2. **Persuasion Check (DC 12)** - Try to negotiate peacefully",
                "3. **Combat** - Attack directly",
                "4. Take a different approach"
            ]
            random.shuffle(options)
            options = options[:4]
        
        # Format options as text
        options_text = "\n".join(options)
        
        # Create scene JSON
        scene_json = {
            "scene_text": scene_text,
            "seed": seed,
            "options": [line.strip() for line in options if line.strip()],
            "generation_method": scenario.get("generation_method", "unknown"),
            "rag_documents_used": scenario.get("rag_documents_used", 0)
        }
        
        return json.dumps(scene_json, indent=2), options_text
    
    def _build_rag_enhanced_prompt(self, query: str, documents: List[Dict[str, Any]], seed: Dict[str, Any]) -> str:
        """
        Build prompt enhanced with RAG context
        
        Args:
            query: Original query/prompt
            documents: Retrieved RAG documents
            seed: Scenario seed information
            
        Returns:
            Enhanced prompt string
        """
        prompt = "You are an expert Dungeon Master creating engaging D&D scenarios using retrieved context.\n\n"
        
        # Add RAG context
        if documents:
            prompt += "Retrieved D&D Context:\n"
            for i, doc in enumerate(documents, 1):
                content = doc.get("content", "")[:300]  # Limit length
                source = doc.get("meta", {}).get("source_file", "Unknown")
                prompt += f"{i}. {content}... (Source: {source})\n"
            prompt += "\n"
        
        # Add seed context
        if seed.get('location'):
            prompt += f"Location: {seed['location']}\n"
        if seed.get('recent'):
            prompt += f"Recent events: {', '.join(seed['recent'])}\n"
        if seed.get('party'):
            prompt += f"Party members: {', '.join(seed['party'])}\n"
        if seed.get('story_arc'):
            prompt += f"Story arc: {seed['story_arc']}\n"
        
        prompt += f"\nScenario Request: {query}\n\n"
        
        # Add generation instructions
        prompt += """Using the retrieved context above, generate an engaging D&D scenario with:

1. **Scene Description** (2-3 sentences): Vivid description incorporating relevant context
2. **Player Options** (3-4 numbered choices): Include mix of:
   - Skill checks (format: "**Skill Check (DC X)** - Description")
   - Combat options (format: "**Combat** - Description (Enemy details)")
   - Social interactions
   - Problem-solving approaches

Ensure the scenario feels authentic to D&D and incorporates relevant retrieved information.
Focus on creativity, engagement, and maintaining story continuity."""
        
        return prompt
    
    def _generate_with_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Generate scenario using LLM
        
        Args:
            prompt: Formatted prompt for generation
            
        Returns:
            Generated scenario dictionary or None if failed
        """
        if not (self.has_llm and self.chat_generator):
            return None
        
        try:
            if CLAUDE_AVAILABLE:
                messages = [ChatMessage.from_user(prompt)]
            else:
                messages = [{"role": "user", "content": prompt}]
            
            response = self.chat_generator.run(messages=messages)
            
            if response and "replies" in response:
                scenario_text = response["replies"][0].text
                return self._parse_scenario_response(scenario_text)
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ ScenarioGenerator: LLM generation failed: {e}")
        
        return None
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario based on current game state using RAG-first approach"""
        if self.verbose:
            print(f"🎭 ScenarioGenerator: Starting RAG-first scenario generation")
        
        # 1. Build scenario seed
        seed = self._seed_scene(state)
        prompt = self._build_creative_prompt(seed)
        
        # 2. Request RAG documents (with timeout)
        documents = self._request_rag_documents(prompt, max_docs=MAX_RAG_DOCUMENTS)
        
        # 3. Generate scenario (RAG-enhanced or creative fallback)
        if documents:
            scenario = self._generate_rag_enhanced_scenario(prompt, documents, seed)
            if self.verbose:
                print(f"✅ ScenarioGenerator: Generated RAG-enhanced scenario with {len(documents)} documents")
        else:
            scenario = self._generate_creative_scenario(prompt, [], seed.get('story_arc', ''), str(seed))
            if self.verbose:
                print(f"🎨 ScenarioGenerator: Generated creative scenario (RAG unavailable)")
        
        # 4. Format and return response
        return self._format_scenario_response(scenario, seed)
    
    def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
        """Apply a player's choice and return the continuation - simplified for sync use"""
        try:
            if self.verbose:
                print(f"⚡ ScenarioGenerator: Processing choice {choice_value} for {player}")
            
            # Extract and validate the chosen option
            current_options = state.get("current_options", "")
            lines = [line for line in current_options.splitlines() if line.strip()]
            target = None
            
            # Try to find the choice by number
            for line in lines:
                if line.strip().startswith(f"{choice_value}."):
                    target = line
                    break
            
            # Fallback: pick by index
            if not target and lines:
                idx = max(0, min(len(lines) - 1, choice_value - 1))
                target = lines[idx]
            
            if not target:
                target = f"Option {choice_value}"
            
            # Build consequence generation prompt
            prompt = self._build_creative_choice_prompt(state, target, player)
            
            # Use creative generation for player choice (sync method)
            consequence = self._generate_creative_scenario(prompt, [], state.get('story_arc', ''), str(state))
            if consequence and consequence.get("scenario_text"):
                if self.verbose:
                    print(f"🎨 ScenarioGenerator: Generated creative consequence")
                return consequence["scenario_text"]
            
            # Final fallback
            return f"{player} chose: {target}"
            
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Error applying player choice: {e}")
            return f"Error applying choice: {e}"
    
    def _seed_scene(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract seed information for scene generation"""
        return {
            "location": state["session"].get("location") or "unknown",
            "recent": state["session"].get("events", [])[-4:],
            "party": list(state.get("players", {}).keys())[:8],
            "story_arc": state.get("story_arc", "")
        }
    
    def _build_prompt(self, seed: Dict[str, Any]) -> str:
        """Build prompt for scenario generation"""
        prompt = (
            f"You are the Dungeon Master. Create a vivid short scene (2-3 sentences) and offer 3-4 numbered options.\n"
            f"Location: {seed['location']}\n"
            f"Recent: {seed['recent']}\n"
            f"Party: {seed['party']}\n"
            f"Story arc: {seed['story_arc']}\n"
            "Return a JSON-like object with fields: scene_text, options_text."
        )
        return prompt
    
    def _build_creative_prompt(self, seed: Dict[str, Any]) -> str:
        """Build prompt for creative scenario generation with skill checks and combat options"""
        return (
            f"Continue this D&D adventure story:\n"
            f"Location: {seed['location']}\n"
            f"Recent events: {', '.join(seed['recent'])}\n"
            f"Party members: {', '.join(seed['party'])}\n"
            f"Story arc: {seed['story_arc']}\n\n"
            "Generate an engaging scene continuation (2-3 sentences) and provide 3-4 numbered options for the players.\n\n"
            "IMPORTANT: Include these types of options:\n"
            "- At least 1-2 options that require SKILL CHECKS (Stealth, Perception, Athletics, Persuasion, Investigation, etc.) with clear success/failure consequences\n"
            "- If appropriate to the scene, include potential COMBAT scenarios with specific enemies/monsters\n"
            "- Mix of direct action, social interaction, and problem-solving options\n\n"
            "For skill check options, format like: '1. **Stealth Check (DC 15)** - Sneak past the guards to avoid confrontation'\n"
            "For combat options, format like: '2. **Combat** - Attack the bandits (2 Bandits, 1 Bandit Captain)'"
        )
    
    def _build_creative_choice_prompt(self, state: Dict[str, Any], choice: str, player: str) -> str:
        """Build prompt for creative choice consequences"""
        return (
            f"In this D&D adventure, {player} chose: {choice}\n"
            f"Current story context: {state.get('story_arc', '')}\n"
            f"Game situation: Location: {state.get('session', {}).get('location', 'unknown')}\n\n"
            "Describe what happens as a result of this choice. Make it engaging and appropriate for D&D."
            "Write 2-3 sentences showing the immediate consequence and outcome.\n\n"
            "IMPORTANT: Include these types of options:\n"
            "- At least 1-2 options that require SKILL CHECKS (Stealth, Perception, Athletics, Persuasion, Investigation, etc.) with clear success/failure consequences\n"
            "- If appropriate to the scene, include potential COMBAT scenarios with specific enemies/monsters\n"
            "- Mix of direct action, social interaction, and problem-solving options\n\n"
            "For skill check options, format like: '1. **Stealth Check (DC 15)** - Sneak past the guards to avoid confrontation'\n"
            "For combat options, format like: '2. **Combat** - Attack the bandits (2 Bandits, 1 Bandit Captain)'"
        )
    
    def _build_choice_consequence_prompt(self, state: Dict[str, Any], choice: str) -> str:
        """Build prompt for choice consequences (RAG fallback)"""
        return (
            f"CONTEXT: {state.get('story_arc')}\n"
            f"CHOICE: {choice}\n"
            "Describe the immediate consequence in 2-3 sentences and return a short 'continuation' field."
        )
    
    def _parse_generation_response(self, response: str) -> Any:
        """Parse scenario generation response"""
        # Try to parse as JSON first
        try:
            return json.loads(response)
        except:
            pass
        
        # Try to extract JSON from text
        import re
        json_pattern = r'\{[^{}]*\}'
        matches = re.findall(json_pattern, response)
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
        
        # Return as string
        return response
    
    def _parse_choice_response(self, response: str) -> Any:
        """Parse choice consequence response"""
        # Try to parse as JSON first
        try:
            return json.loads(response)
        except:
            pass
        
        # Return as string
        return response
    
    def _generate_creative_scenario(self, query: str, documents: List[Dict],
                                   campaign_context: str, game_state: str) -> Dict[str, Any]:
        """Generate creative scenario with optional RAG context"""
        
        # Build context-aware prompt
        prompt = self._build_scenario_prompt(query, documents, campaign_context, game_state)
        
        if self.has_llm and self.chat_generator:
            # Use LLM for creative generation
            try:
                if CLAUDE_AVAILABLE:
                    messages = [ChatMessage.from_user(prompt)]
                else:
                    messages = [{"role": "user", "content": prompt}]
                    
                response = self.chat_generator.run(messages=messages)
                
                if response and "replies" in response:
                    scenario_text = response["replies"][0].text
                    return self._parse_scenario_response(scenario_text)
                    
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ LLM generation failed: {e}")
        
        # Fallback generation
        return self._generate_fallback_scenario(query, documents)

    def _build_scenario_prompt(self, query: str, documents: List[Dict],
                              campaign_context: str, game_state: str) -> str:
        """Build comprehensive scenario generation prompt"""
        prompt = "You are an expert Dungeon Master creating engaging D&D scenarios.\n\n"
        
        # Add RAG context if available
        if documents:
            prompt += "Relevant D&D context:\n"
            for i, doc in enumerate(documents, 1):
                content = doc.get("content", "")[:200]  # Limit length
                source = doc.get("meta", {}).get("source_file", "Unknown")
                prompt += f"{i}. {content}... (Source: {source})\n"
            prompt += "\n"
        
        # Add campaign context
        if campaign_context:
            prompt += f"Campaign Context: {campaign_context}\n"
        
        # Add game state
        if game_state:
            prompt += f"Current Game State: {game_state}\n"
        
        prompt += f"\nPlayer Request: {query}\n\n"
        
        # Add generation instructions
        prompt += """Generate an engaging D&D scenario with the following structure:

1. **Scene Description** (2-3 sentences): Vivid description of the current situation
2. **Player Options** (3-4 numbered choices): Include mix of:
   - Skill checks (format: "**Skill Check (DC X)** - Description")
   - Combat options (format: "**Combat** - Description (Enemy details)")
   - Social interactions
   - Problem-solving approaches

Ensure options are clearly numbered and formatted for easy selection.
Focus on creativity, engagement, and D&D authenticity."""
        
        return prompt

    def _parse_scenario_response(self, scenario_text: str) -> Dict[str, Any]:
        """Parse scenario response into structured format"""
        # Split into scene description and options
        lines = scenario_text.split('\n')
        scene_lines = []
        options = []
        
        in_options = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this looks like a numbered option
            if re.match(r'^\d+\.', line) or (line.startswith('**') and ('Check' in line or 'Combat' in line)):
                in_options = True
                options.append(line)
            elif in_options:
                # Still in options section
                if line.startswith('-') or re.match(r'^\d+', line):
                    options.append(line)
                else:
                    # Back to description
                    scene_lines.append(line)
            else:
                scene_lines.append(line)
        
        scene_text = ' '.join(scene_lines) if scene_lines else scenario_text
        
        # If no options parsed, create fallback
        if not options:
            options = [
                "1. **Investigation Check (DC 15)** - Examine the area carefully",
                "2. **Persuasion Check (DC 12)** - Try to negotiate peacefully",
                "3. **Combat** - Attack directly",
                "4. Take a different approach"
            ]
        
        return {
            "scenario_text": scene_text,
            "options": options,
            "generation_method": "creative_llm" if self.has_llm else "fallback"
        }

    def _generate_fallback_scenario(self, query: str, documents: List[Dict]) -> Dict[str, Any]:
        """Generate fallback scenario when LLM unavailable"""
        # Basic scenario based on query keywords
        scene_templates = {
            "tavern": "The party enters a bustling tavern filled with the aroma of roasted meat and ale. Conversations hush as suspicious eyes turn toward the newcomers. A hooded figure in the corner gestures subtly toward your group.",
            "dungeon": "Ancient stone walls drip with moisture as your torchlight flickers across mysterious runes. The air grows thick with an otherworldly presence, and distant echoes suggest you are not alone in these forgotten depths.",
            "forest": "Sunlight filters through the canopy above as the party travels along an overgrown path. Suddenly, the natural sounds of the forest fall silent, and you notice fresh tracks leading into the undergrowth.",
            "city": "The crowded streets buzz with activity as merchants hawk their wares and guards patrol their beats. Your party notices unusual commotion near the city gates, with whispered conversations and furtive glances.",
        }
        
        # Try to match query to template
        query_lower = query.lower()
        scene_text = scene_templates.get("tavern")  # Default
        
        for location, template in scene_templates.items():
            if location in query_lower:
                scene_text = template
                break
        
        # Add RAG context if available
        if documents:
            scene_text += f" (Enhanced with {len(documents)} D&D references from your knowledge base.)"
        
        options = [
            "1. **Perception Check (DC 15)** - Look around carefully for clues",
            "2. **Investigation Check (DC 12)** - Search the immediate area",
            "3. **Persuasion Check (DC 14)** - Approach and ask questions",
            "4. Stay alert and observe from a distance"
        ]
        
        return {
            "scenario_text": scene_text,
            "options": options,
            "generation_method": "fallback"
        }

    def _handle_game_state_updated(self, message: AgentMessage):
        """Handle game_state_updated event - no action needed for scenario generator"""
        # Scenario generator doesn't need to respond to game state updates directly
        # This handler exists only to prevent "no handler" error messages
        pass

    def _handle_campaign_selected(self, message: AgentMessage):
        """Handle campaign_selected event - validate message data and acknowledge"""
        # Validate message data - fix for 'str' object has no attribute 'get' error
        if not isinstance(message.data, dict):
            if self.verbose:
                print(f"⚠️ ScenarioGenerator received invalid campaign_selected data type: {type(message.data)}")
            # Convert to dict if it's a string (common issue)
            if isinstance(message.data, str):
                try:
                    import json
                    message.data = json.loads(message.data)
                except:
                    message.data = {"campaign_name": message.data}
            else:
                message.data = {"campaign_name": "unknown"}
        
        # Fix: Look for 'campaign' field (sent by campaign_manager) instead of 'campaign_name'
        campaign_name = message.data.get("campaign", message.data.get("campaign_name", "unknown"))
        if self.verbose:
            print(f"📋 ScenarioGenerator acknowledged campaign selection: {campaign_name}")
        
        # No response needed for broadcast events - just acknowledge receipt

    def process_tick(self):
        """Process scenario generator tick - mostly reactive, no regular processing needed"""
        # Clean up expired RAG requests periodically to prevent memory leaks
        self._cleanup_expired_requests()

