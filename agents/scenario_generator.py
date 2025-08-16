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
        
        # Setup handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup message handlers for scenario generator"""
        self.register_handler("generate_scenario", self._handle_generate_scenario)
        self.register_handler("generate_with_context", self._handle_generate_with_context)
        self.register_handler("apply_player_choice", self._handle_apply_player_choice)
        self.register_handler("get_generator_status", self._handle_get_generator_status)
    
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
    
    def _handle_generate_scenario(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle scenario generation request"""
        game_state = message.data.get("game_state")
        if not game_state:
            return {"success": False, "error": "No game state provided"}
        
        try:
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
            return {"success": False, "error": str(e)}
    
    def _handle_apply_player_choice(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle player choice application"""
        game_state = message.data.get("game_state")
        player = message.data.get("player")
        choice = message.data.get("choice")
        
        if not all([game_state, player, choice]):
            return {"success": False, "error": "Missing game state, player, or choice"}
        
        try:
            continuation = self.apply_player_choice(game_state, player, choice)
            return {"success": True, "continuation": continuation}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_generator_status(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle generator status request - updated for orchestrator communication"""
        return {
            "llm_available": self.has_llm,
            "chat_generator_available": self.chat_generator is not None,
            "verbose": self.verbose,
            "agent_type": self.agent_type,
            "uses_orchestrator_communication": True  # New flag
        }
    
    def _handle_generate_with_context(self, message: AgentMessage) -> Dict[str, Any]:
        """Generate scenario with optional RAG context - orchestrator communication"""
        query = message.data.get("query")
        use_rag = message.data.get("use_rag", True)
        campaign_context = message.data.get("campaign_context", "")
        game_state = message.data.get("game_state", "")
        
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            # Retrieve relevant documents via orchestrator
            documents = []
            if use_rag:
                # Use the correct handler name from haystack pipeline agent
                rag_response = self.send_message("haystack_pipeline", "retrieve_documents", {
                    "query": query,
                    "max_docs": 3
                })
                
                # Handle orchestrator response properly
                if rag_response and rag_response.get("success"):
                    documents = rag_response.get("documents", [])
                elif self.verbose:
                    print(f"⚠️ RAG document retrieval failed or unavailable")
            
            # Generate scenario with or without RAG context
            scenario = self._generate_creative_scenario(query, documents, campaign_context, game_state)
            
            return {
                "success": True,
                "scenario": scenario,
                "used_rag": len(documents) > 0,
                "source_count": len(documents)
            }
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Scenario generation error: {e}")
            return {"success": False, "error": str(e)}
    
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

    def process_tick(self):
        """Process scenario generator tick - mostly reactive, no regular processing needed"""
        pass


# class ScenarioGenerator:
    """Traditional ScenarioGenerator class for backward compatibility - orchestrator communication"""
    
    def __init__(self, haystack_agent=None, verbose: bool = False):
        # Ignore haystack_agent parameter for backward compatibility
        # but don't store it - use orchestrator communication instead
        self.verbose = verbose
        self._agent_communication_available = False
        
        # Try to detect if we're in an agent environment
        try:
            # This will be set when the ScenarioGeneratorAgent is used in orchestrator
            self._scenario_agent = None  # Will be set by orchestrator if available
        except Exception:
            pass
    
    def _query_via_orchestrator(self, action: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt to query via orchestrator if available"""
        if self._scenario_agent and hasattr(self._scenario_agent, 'send_message'):
            try:
                return self._scenario_agent.send_message("haystack_pipeline", action, data)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Orchestrator query failed: {e}")
        return None
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario - orchestrator communication fallback"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        # Try orchestrator communication for RAG context
        try:
            prompt = self._build_prompt(seed)
            rag_response = self._query_via_orchestrator("retrieve_documents", {
                "query": prompt,
                "max_docs": 3
            })
            
            if rag_response and rag_response.get("success"):
                documents = rag_response.get("documents", [])
                if documents and self.verbose:
                    print(f"📚 Enhanced scenario with {len(documents)} RAG documents")
                    # Simple enhancement based on RAG context
                    scene_text += f" (Enhanced with {len(documents)} D&D references from knowledge base.)"
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Backward compatibility RAG query failed: {e}")
        
        # Generate fallback options
        if not options_text:
            options = [
                "1. Investigate the suspicious noise.",
                "2. Approach openly and ask questions.",
                "3. Set up an ambush and wait.",
                "4. Leave and gather more information."
            ]
            random.shuffle(options)
            options_text = "\n".join(options[:4])
        
        scene_json = {
            "scene_text": scene_text,
            "seed": seed,
            "options": [line.strip() for line in options_text.splitlines() if line.strip()]
        }
        return json.dumps(scene_json, indent=2), options_text
    
    def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
        """Apply player choice - orchestrator communication fallback"""
        try:
            current_options = state.get("current_options", "")
            lines = [l for l in current_options.splitlines() if l.strip()]
            target = None
            
            # Try numeric match
            for l in lines:
                if l.strip().startswith(f"{choice_value}."):
                    target = l
                    break
            
            if not target and lines:
                idx = max(0, min(len(lines) - 1, choice_value - 1))
                target = lines[idx]
            
            if not target:
                return f"No such option: {choice_value}"
            
            continuation = f"{player} chose: {target}"
            
            # Try orchestrator communication for consequence enhancement
            try:
                prompt = f"CONTEXT: {state.get('story_arc')}\nCHOICE: {target}\nDescribe the immediate consequence in 2-3 sentences."
                rag_response = self._query_via_orchestrator("retrieve_documents", {
                    "query": prompt,
                    "max_docs": 2
                })
                
                if rag_response and rag_response.get("success"):
                    documents = rag_response.get("documents", [])
                    if documents:
                        continuation += f" (Enhanced with {len(documents)} D&D rule references.)"
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Backward compatibility choice consequence failed: {e}")
            
            return continuation
            
        except Exception as e:
            return f"Error applying choice: {e}"
    
    # Keep existing helper methods unchanged
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
        return (
            f"You are the Dungeon Master. Create a vivid short scene (2-3 sentences) and offer 3-4 numbered options.\n"
            f"Location: {seed['location']}\nRecent: {seed['recent']}\nParty: {seed['party']}\nStory arc: {seed['story_arc']}\n"
            "Return a JSON-like object with fields: scene_text, options_text."
        )