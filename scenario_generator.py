"""
Scenario Generator for DM Assistant
Generates dynamic scenarios and handles player choices using RAG and LLM
"""
import json
import random
from typing import Dict, List, Any, Optional, Tuple

from agent_framework import BaseAgent, MessageType, AgentMessage
try:
    from rag_agent_integrated import RAGAgent
except ImportError:
    from rag_agent import RAGAgent

# Claude-specific imports
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class ScenarioGeneratorAgent(BaseAgent):
    """Scenario Generator as an agent that creates dynamic scenarios and handles player choices"""
    
    def __init__(self, rag_agent: Optional[RAGAgent] = None, verbose: bool = False):
        super().__init__("scenario_generator", "ScenarioGenerator")
        self.rag_agent = rag_agent
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
            "rag_available": self.rag_agent is not None,
            "llm_available": self.has_llm,
            "verbose": self.verbose,
            "agent_type": self.agent_type
        }
    
    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        """Generate a new scenario based on current game state"""
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        
        if self.rag_agent:
            try:
                prompt = self._build_prompt(seed)
                result = self.rag_agent.query(prompt)
                
                if "error" not in result:
                    answer = result.get("answer", "")
                    parsed_response = self._parse_generation_response(answer)
                    
                    if isinstance(parsed_response, dict):
                        scene_text = parsed_response.get("scene_text", scene_text)
                        options_text = parsed_response.get("options_text", "")
                    elif isinstance(parsed_response, str):
                        # Treat as scene text
                        scene_text = parsed_response
            except Exception as e:
                if self.verbose:
                    print(f"Error in scenario generation: {e}")
        
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
                return f"No such option: {choice_value}"
            
            continuation = f"{player} chose: {target}"
            
            # Use RAG agent to generate consequences if available
            if self.rag_agent:
                prompt = self._build_choice_consequence_prompt(state, target)
                try:
                    result = self.rag_agent.query(prompt)
                    if "error" not in result:
                        answer = result.get("answer", "")
                        parsed_response = self._parse_choice_response(answer)
                        
                        if isinstance(parsed_response, dict):
                            return parsed_response.get("continuation", continuation)
                        elif isinstance(parsed_response, str):
                            return parsed_response
                except Exception:
                    pass
            
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
    
    def _build_choice_consequence_prompt(self, state: Dict[str, Any], choice: str) -> str:
        """Build prompt for choice consequences"""
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
    
    def __init__(self, rag_agent: Optional[RAGAgent] = None, verbose: bool = False):
        self.rag_agent = rag_agent
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
        
        if self.rag_agent:
            try:
                prompt = self._build_prompt(seed)
                resp = self.rag_agent.query(prompt)
                if isinstance(resp, dict):
                    scene_text = resp.get("scene_text", scene_text)
                    options_text = resp.get("options_text", "")
                elif isinstance(resp, str):
                    # Quick heuristic: treat as scene_text
                    scene_text = resp
            except Exception:
                pass
        
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
            
            # Ask rag agent for consequence
            if self.rag_agent:
                prompt = (
                    f"CONTEXT: {state.get('story_arc')}\nCHOICE: {target}\n"
                    "Describe the immediate consequence in 2-3 sentences and return a short 'continuation' field."
                )
                try:
                    resp = self.rag_agent.query(prompt)
                    if isinstance(resp, dict):
                        return resp.get("continuation", cont)
                    elif isinstance(resp, str):
                        return resp
                except Exception:
                    pass
            
            return cont
            
        except Exception as e:
            return f"Error applying choice: {e}"