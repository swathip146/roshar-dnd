"""
Scenario Generator for DM Assistant
Generates dynamic scenarios and handles player choices using RAG and LLM
"""
import json
import random
from typing import Dict, List, Any, Optional, Tuple

from agent_framework import BaseAgent, MessageType, AgentMessage
from haystack_pipeline_agent import HaystackPipelineAgent

# Claude-specific imports
CLAUDE_AVAILABLE = True



class ScenarioGeneratorAgent(BaseAgent):
    """Scenario Generator as an agent that creates dynamic scenarios and handles player choices"""
    
    def __init__(self, haystack_agent: Optional[HaystackPipelineAgent] = None, verbose: bool = False):
        super().__init__("scenario_generator", "ScenarioGenerator")
        self.haystack_agent = haystack_agent
        self.verbose = verbose
        self.has_llm = CLAUDE_AVAILABLE
    
    def _setup_handlers(self):
        """Setup message handlers for scenario generator"""
        self.register_handler("generate_scenario", self._handle_generate_scenario)
        self.register_handler("apply_player_choice", self._handle_apply_player_choice)
        self.register_handler("get_generator_status", self._handle_get_generator_status)
    
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
        """Handle generator status request"""
        return {
            "haystack_available": self.haystack_agent is not None,
            "llm_available": self.has_llm,
            "verbose": self.verbose,
            "agent_type": self.agent_type
        }
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario based on current game state"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        # Try creative scenario generation first via HaystackPipelineAgent
        if self.haystack_agent:
            try:
                prompt = self._build_creative_prompt(seed)
                # Send message to haystack agent through orchestrator
                message_id = self.send_message("haystack_pipeline", "query_scenario", {
                    "query": prompt,
                    "campaign_context": seed.get('story_arc', ''),
                    "game_state": str(seed)
                })
                
                if message_id:
                    # Note: In agent architecture, we don't wait for responses synchronously
                    # The response will be handled by the orchestrator
                    if self.verbose:
                        print("📤 Sent scenario generation request to haystack pipeline")
                        
            except Exception as e:
                if self.verbose:
                    print(f"Error in creative scenario generation: {str(e)}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
        
        # If haystack agent failed or unavailable, use basic fallback
        elif not self.haystack_agent:
            if self.verbose:
                print("No Haystack agent available, using basic scenario generation")
        
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
        """Apply a player's choice and return the continuation"""
        try:
            current_options = state.get("current_options", "")
            # if self.verbose:
            #     print(f"DEBUG: current_options = {current_options}")
            #     print(f"DEBUG: choice_value = {choice_value}")
            
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
                # Use a generic choice description
                target = f"Option {choice_value}"
            
            continuation = f"{player} chose: {target}"
            
            # Try creative consequence generation first via HaystackPipelineAgent
            if self.haystack_agent:
                prompt = self._build_creative_choice_prompt(state, target, player)
                try:
                    # Send message to haystack agent through orchestrator
                    message_id = self.send_message("haystack_pipeline", "query_scenario", {
                        "query": prompt,
                        "campaign_context": state.get('story_arc', ''),
                        "game_state": str(state)
                    })
                    
                    if message_id:
                        if self.verbose:
                            print("📤 Sent choice consequence request to haystack pipeline")
                        # In agent architecture, return basic continuation since we can't wait synchronously
                        # The detailed response will be handled by the orchestrator
                        
                except Exception as e:
                    if self.verbose:
                        print(f"Error in creative choice consequence generation: {str(e)}")
                        import traceback
                        print(f"Traceback: {traceback.format_exc()}")
            
            # If haystack agent failed or unavailable, use basic continuation
            elif not self.haystack_agent:
                if self.verbose:
                    print("No Haystack agent available for choice consequence generation")
            
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
    
    def process_tick(self):
        """Process scenario generator tick - mostly reactive, no regular processing needed"""
        pass


class ScenarioGenerator:
    """Traditional ScenarioGenerator class for backward compatibility"""
    
    def __init__(self, haystack_agent: Optional[HaystackPipelineAgent] = None, verbose: bool = False):
        self.haystack_agent = haystack_agent
        self.verbose = verbose
    
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
            f"Location: {seed['location']}\nRecent: {seed['recent']}\nParty: {seed['party']}\nStory arc: {seed['story_arc']}\n"
            "Return a JSON-like object with fields: scene_text, options_text."
        )
        return prompt
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        if self.haystack_agent:
            try:
                prompt = self._build_prompt(seed)
                response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_scenario", {
                    "query": prompt,
                    "campaign_context": seed.get('story_arc', ''),
                    "game_state": str(seed)
                }, timeout=30.0)
                
                if response and response.get("success"):
                    result = response.get("result", {})
                    answer = result.get("answer", "")
                    
                    # Try to parse the response
                    if isinstance(answer, str) and len(answer) > 50:
                        scene_text = answer
            except Exception as e:
                if self.verbose:
                    print(f"Error in backward compatibility scenario generation: {str(e)}")
        
        if not options_text:
            # Fallback options
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
        """Apply player choice and return continuation"""
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
                # Fallback: pick by index
                idx = max(0, min(len(lines) - 1, choice_value - 1))
                target = lines[idx]
            
            if not target:
                return f"No such option: {choice_value}"
            
            cont = f"{player} chose: {target}"
            
            # Ask haystack agent for consequence
            if self.haystack_agent:
                prompt = (
                    f"CONTEXT: {state.get('story_arc')}\nCHOICE: {target}\n"
                    "Describe the immediate consequence in 2-3 sentences and return a short 'continuation' field."
                )
                try:
                    response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_scenario", {
                        "query": prompt,
                        "campaign_context": state.get('story_arc', ''),
                        "game_state": str(state)
                    }, timeout=30.0)
                    
                    if response and response.get("success"):
                        result = response.get("result", {})
                        answer = result.get("answer", "")
                        if isinstance(answer, str) and len(answer) > 10:
                            return answer
                except Exception as e:
                    if self.verbose:
                        print(f"Error in backward compatibility choice consequence generation: {str(e)}")
            
            return cont
            
        except Exception as e:
            return f"Error applying choice: {e}"