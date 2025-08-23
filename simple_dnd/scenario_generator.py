#!/usr/bin/env python3
"""
Basic scenario generation with minimal structure - Week 2 Implementation
"""
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
from hwtgenielib.dataclasses import ChatMessage
from typing import Dict, List, Any, Optional
from .config import GameConfig, DEFAULT_CONFIG

class SimpleScenarioGenerator:
    """Basic scenario generation with minimal structure"""
    
    def __init__(self, config: Optional[GameConfig] = None):
        """Initialize the scenario generator"""
        self.config = config or DEFAULT_CONFIG
        self.chat_generator = AppleGenAIChatGenerator(
            model=self.config.model_name
        )
    
    def generate_scenario(self, context: str = "tavern") -> Dict[str, Any]:
        """Generate simple scenario"""
        
        # Get context description
        context_desc = self.config.get_context_description(context)
        
        prompt = f"""Create a D&D scenario in a {context}.

Context: {context_desc}

Include:
- Brief scene description (2-3 sentences)
- 3 clear player choices
- Keep it simple and engaging

Format:
SCENE: [description]
CHOICE 1: [option]
CHOICE 2: [option] 
CHOICE 3: [option]"""

        try:
            messages = [ChatMessage.from_user(prompt)]
            response = self.chat_generator.run(messages=messages)
            
            if response and "replies" in response:
                return self._parse_simple_response(response["replies"][0].text)
        
        except Exception as e:
            print(f"❌ Error generating scenario: {e}")
        
        # Fallback scenario
        return self._fallback_scenario(context)
    
    def _parse_simple_response(self, text: str) -> Dict[str, Any]:
        """Basic text parsing"""
        lines = text.split('\n')
        
        scene = ""
        choices = []
        
        for line in lines:
            line = line.strip()
            if line.startswith("SCENE:"):
                scene = line.replace("SCENE:", "").strip()
            elif line.startswith("CHOICE"):
                choice = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                if choice:
                    choices.append(choice)
        
        # Ensure we have a scene and choices
        if not scene:
            scene = "You find yourself in an interesting situation."
        
        if len(choices) < 3:
            choices.extend([
                "Look around carefully",
                "Approach cautiously", 
                "Wait and observe"
            ][:3-len(choices)])
        
        return {
            "scene": scene, 
            "choices": choices[:3],  # Limit to 3 choices
            "context": "tavern"
        }
    
    def _fallback_scenario(self, context: str) -> Dict[str, Any]:
        """Fallback scenario when generation fails"""
        fallback_scenarios = {
            "tavern": {
                "scene": "You find yourself in a quiet tavern. The bartender polishes glasses while a hooded figure sits alone in the corner.",
                "choices": [
                    "Talk to the bartender about local rumors",
                    "Approach the hooded figure",
                    "Order a drink and listen to conversations"
                ]
            },
            "forest": {
                "scene": "You're on a forest path when you hear rustling in the bushes ahead. Sunlight filters through the canopy above.",
                "choices": [
                    "Investigate the rustling sound",
                    "Continue down the path cautiously",
                    "Hide behind a tree and wait"
                ]
            },
            "dungeon": {
                "scene": "You stand before a heavy wooden door bound with iron. Torch light flickers on damp stone walls.",
                "choices": [
                    "Try to open the door",
                    "Listen at the door first",
                    "Search for another way around"
                ]
            }
        }
        
        return fallback_scenarios.get(context, fallback_scenarios["tavern"])