"""
Scenario Generator for DM Assistant
Generates dynamic scenarios and handles player choices using RAG and LLM
"""
import json
import random
import re
from typing import Dict, List, Any, Optional, Tuple

from agent_framework import BaseAgent, MessageType, AgentMessage
# REMOVED: from agents.haystack_pipeline_agent import HaystackPipelineAgent - direct coupling removed

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



class ScenarioGeneratorAgent(BaseAgent):
    """Scenario Generator as an agent that creates dynamic scenarios and handles player choices"""
    
    def __init__(self, verbose: bool = False):  # Remove haystack_agent parameter entirely
        super().__init__("scenario_generator", "ScenarioGenerator")
        self.verbose = verbose
        self.has_llm = CLAUDE_AVAILABLE
        # Remove: self.haystack_agent = haystack_agent
        
        # Initialize LLM for creative generation
        if self.has_llm:
            try:
                self.chat_generator = AppleGenAIChatGenerator(
                    model= LLM_MODEL
                )
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed to initialize LLM: {e}")
                self.chat_generator = None
                self.has_llm = False
        else:
            self.chat_generator = None
        
        # Note: _setup_handlers() is already called by BaseAgent.__init__()
    
    def _setup_handlers(self):
        """Setup message handlers for scenario generator"""
        self.register_handler("generate_scenario", self._handle_generate_scenario)
        self.register_handler("generate_with_context", self._handle_generate_with_context)
        self.register_handler("apply_player_choice", self._handle_apply_player_choice)
        self.register_handler("get_generator_status", self._handle_get_generator_status)
        self.register_handler("game_state_updated", self._handle_game_state_updated)
        self.register_handler("campaign_selected", self._handle_campaign_selected)
        self.register_handler("retrieve_documents", self._handle_retrieve_documents)
    
    def _is_haystack_pipeline_available(self) -> bool:
        """Check if haystack pipeline is available via orchestrator communication"""
        try:
            # Send status request to haystack pipeline agent
            status_response = self.send_message("haystack_pipeline", "get_pipeline_status", {})
            
            # Note: In agent architecture, we can't wait for synchronous responses
            # So we assume availability and handle errors gracefully in actual queries
            return True
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Unable to check haystack pipeline status: {e}")
            return False
    
    def _handle_generate_scenario(self, message: AgentMessage):
        """Handle scenario generation request"""
        game_state = message.data.get("game_state")
        if not game_state:
            self.send_response(message, {"success": False, "error": "No game state provided"})
            return
        
        try:
            scene_json, options_text = self.generate(game_state)
            
            # Send the generated scenario back to game engine
            self.send_message("game_engine", "add_scene_to_history", {
                "scene_data": scene_json,
                "options_text": options_text
            })
            
            self.send_response(message, {
                "success": True,
                "scene_json": scene_json,
                "options_text": options_text
            })
        except Exception as e:
            self.send_response(message, {"success": False, "error": str(e)})
    
    def _handle_apply_player_choice(self, message: AgentMessage):
        """Handle player choice application"""
        game_state = message.data.get("game_state")
        player = message.data.get("player")
        choice = message.data.get("choice")
        
        if not all([game_state, player, choice]):
            self.send_response(message, {"success": False, "error": "Missing game state, player, or choice"})
            return
        
        try:
            continuation = self.apply_player_choice(game_state, player, choice)
            self.send_response(message, {"success": True, "continuation": continuation})
        except Exception as e:
            self.send_response(message, {"success": False, "error": str(e)})
    
    def _handle_get_generator_status(self, message: AgentMessage):
        """Handle generator status request - updated for orchestrator communication"""
        self.send_response(message, {
            "llm_available": self.has_llm,
            "chat_generator_available": self.chat_generator is not None,
            "verbose": self.verbose,
            "agent_type": self.agent_type,
            "uses_orchestrator_communication": True  # New flag
        })
    
    def _handle_generate_with_context(self, message: AgentMessage):
        """Generate scenario with optional RAG context - orchestrator communication"""
        try:
            if self.verbose:
                print(f"🔥 ScenarioGenerator: Processing generate_with_context request")
            
            # Validate message data first
            if not isinstance(message.data, dict):
                if self.verbose:
                    print(f"❌ ScenarioGenerator: Invalid message data type: {type(message.data)}")
                self.send_response(message, {"success": False, "error": "Invalid message data format"})
                return
            
            query = message.data.get("query")
            use_rag = message.data.get("use_rag", True)
            campaign_context = message.data.get("campaign_context", "")
            game_state = message.data.get("game_state", "")
            
            if self.verbose:
                print(f"🔥 ScenarioGenerator: Query={query}, use_rag={use_rag}")
            
            if not query:
                if self.verbose:
                    print(f"❌ ScenarioGenerator: No query provided")
                self.send_response(message, {"success": False, "error": "No query provided"})
                return
            
            # For now, skip RAG retrieval since it requires asynchronous handling
            # Generate scenario without RAG context for immediate response
            documents = []
            
            if self.verbose:
                print(f"🔥 ScenarioGenerator: Calling _generate_creative_scenario")
            
            # Generate scenario with or without RAG context
            scenario = self._generate_creative_scenario(query, documents, campaign_context, game_state)
            
            if self.verbose:
                print(f"🔥 ScenarioGenerator: Generated scenario: {scenario}")
            
            response_data = {
                "success": True,
                "scenario": scenario,
                "used_rag": len(documents) > 0,
                "source_count": len(documents)
            }
            
            if self.verbose:
                print(f"🔥 ScenarioGenerator: Sending response: {response_data}")
            
            self.send_response(message, response_data)
            
            if self.verbose:
                print(f"✅ ScenarioGenerator: Response sent successfully")
                
        except Exception as e:
            if self.verbose:
                print(f"❌ ScenarioGenerator: Exception in handler: {e}")
                import traceback
                print(f"❌ ScenarioGenerator: Traceback: {traceback.format_exc()}")
            
            self.send_response(message, {"success": False, "error": str(e)})
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario based on current game state - orchestrator communication"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        # Try creative scenario generation via orchestrator (remove non-existent query_scenario)
        try:
            prompt = self._build_creative_prompt(seed)
            
            # First try to get RAG context for scenario generation
            documents = []
            rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                "query": prompt,
                "max_docs": 3
            })
            
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
            
            # Generate creative scenario with RAG context
            if documents or self.has_llm:
                scenario = self._generate_creative_scenario(prompt, documents,
                                                          seed.get('story_arc', ''), str(seed))
                if scenario and scenario.get("scenario_text"):
                    scene_text = scenario["scenario_text"]
                    if scenario.get("options"):
                        options_text = "\n".join(scenario["options"])
            
            if self.verbose:
                print(f"📤 Generated scenario via orchestrator communication (RAG docs: {len(documents)})")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Orchestrator scenario generation failed: {e}")
        
        # Generate fallback options if needed
        if not options_text:
            options = [
                "1. Investigate the suspicious noise.",
                "2. Approach openly and ask questions.",
                "3. Set up an ambush and wait.",
                "4. Leave and gather more information."
            ]
            random.shuffle(options)
            options_text = "\n".join(options[:4])
        
        # Create scene JSON
        scene_json = {
            "scene_text": scene_text,
            "seed": seed,
            "options": [line.strip() for line in options_text.splitlines() if line.strip()]
        }
        
        return json.dumps(scene_json, indent=2), options_text
    
    def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
        """Apply a player's choice and return the continuation - orchestrator communication"""
        try:
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
            
            continuation = f"{player} chose: {target}"
            
            # Try creative consequence generation via orchestrator
            try:
                prompt = self._build_creative_choice_prompt(state, target, player)
                
                # Get RAG context for consequence generation
                rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                    "query": prompt,
                    "max_docs": 2
                })
                
                documents = []
                if rag_response and rag_response.get("success"):
                    documents = rag_response.get("documents", [])
                
                # Generate consequence with RAG context
                if documents or self.has_llm:
                    consequence = self._generate_creative_scenario(prompt, documents,
                                                               state.get('story_arc', ''), str(state))
                    if consequence and consequence.get("scenario_text"):
                        return consequence["scenario_text"]
                
                if self.verbose:
                    print("📤 Generated choice consequence via orchestrator communication")
                    
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Orchestrator choice consequence generation failed: {e}")
            
            return continuation
            
        except Exception as e:
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

    def _handle_retrieve_documents(self, message: AgentMessage):
        """Handle retrieve_documents response from haystack_pipeline"""
        # This handler receives the async response from haystack_pipeline.retrieve_documents
        if self.verbose:
            print(f"📄 ScenarioGenerator received retrieve_documents response")
        
        # Store the response for any pending RAG operations
        # For now, just acknowledge receipt - full async RAG integration would require
        # more complex state management to match responses to original requests
        documents = message.data.get("documents", [])
        success = message.data.get("success", False)
        
        if self.verbose:
            print(f"📄 Retrieved {len(documents)} documents, success: {success}")
        
        # Note: This is a response handler, so no response is sent back
        # The actual RAG integration would need to be refactored for proper async handling

    def process_tick(self):
        """Process scenario generator tick - mostly reactive, no regular processing needed"""
        pass

