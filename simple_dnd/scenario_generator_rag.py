#!/usr/bin/env python3
"""
Enhanced scenario generator with RAG support - Stage 2 Week 5-6
Builds on Stage 1 scenario generator by adding Haystack RAG integration
"""
from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
from hwtgenielib.dataclasses import ChatMessage
from typing import Dict, List, Any, Optional
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from storage.simple_document_store import SimpleDocumentStore
from .config import GameConfig, DEFAULT_CONFIG

class RAGScenarioGenerator:
    """Enhanced scenario generator with basic RAG support"""
    
    def __init__(self, config: Optional[GameConfig] = None, document_store: Optional[SimpleDocumentStore] = None):
        """Initialize the RAG-enhanced scenario generator"""
        self.config = config or DEFAULT_CONFIG
        
        # Initialize hwtgenielib chat generator
        self.chat_generator = AppleGenAIChatGenerator(
            model=self.config.model_name
        )
        
        # Initialize or use provided document store
        if document_store:
            self.document_store = document_store
        else:
            self.document_store = SimpleDocumentStore()
            self.document_store.load_basic_content()
        
        print("🎭 RAG Scenario Generator initialized")
    
    def generate_scenario(self, context: str = "tavern", campaign: Optional[str] = None) -> Dict[str, Any]:
        """Generate scenario with optional RAG context"""
        
        # Get RAG context if campaign is specified
        rag_context = ""
        if campaign:
            rag_context = self._get_campaign_context(campaign, context)
        
        # Build enhanced prompt with RAG context
        prompt = self._build_enhanced_prompt(context, rag_context)
        
        try:
            # Generate with hwtgenielib
            messages = [ChatMessage.from_user(prompt)]
            response = self.chat_generator.run(messages=messages)
            
            if response and "replies" in response:
                scenario_text = response["replies"][0].text
                return self._parse_enhanced_response(scenario_text, context, campaign)
        
        except Exception as e:
            print(f"❌ RAG scenario generation failed: {e}")
        
        # Fallback to basic scenario
        return self._fallback_scenario(context, campaign)
    
    def _get_campaign_context(self, campaign: str, context: str) -> str:
        """Get relevant campaign context using RAG"""
        try:
            # Create search queries for different aspects
            queries = [
                f"campaign {campaign}",
                f"{context} in {campaign}",
                f"{campaign} {context} location",
                f"{campaign} NPCs characters"
            ]
            
            all_docs = []
            for query in queries:
                docs = self.document_store.simple_search(query, top_k=2)
                all_docs.extend(docs)
            
            # Combine and limit total context length
            combined_context = "\n".join(all_docs)
            
            # Truncate if too long (keep under 1000 chars for prompt efficiency)
            if len(combined_context) > 1000:
                combined_context = combined_context[:1000] + "..."
            
            return combined_context
            
        except Exception as e:
            print(f"⚠️ Failed to get campaign context: {e}")
            return ""
    
    def _build_enhanced_prompt(self, context: str, rag_context: str) -> str:
        """Build enhanced prompt with RAG context"""
        
        # Get base context description
        context_desc = self.config.get_context_description(context)
        
        prompt = f"""Create an engaging D&D scenario in a {context}.

Context Setting: {context_desc}

{f"Campaign Background: {rag_context}" if rag_context else ""}

Create a scenario that includes:
- A vivid scene description (2-3 sentences) that sets the mood
- 3 meaningful player choices that lead to different outcomes
- Incorporate any relevant campaign details if provided
- Keep it engaging and appropriate for D&D adventure

Format your response as:
SCENE: [vivid description of the current situation]
CHOICE 1: [first meaningful option]
CHOICE 2: [second meaningful option] 
CHOICE 3: [third meaningful option]

Make each choice distinct and interesting, with clear consequences."""

        return prompt
    
    def _parse_enhanced_response(self, text: str, context: str, campaign: Optional[str]) -> Dict[str, Any]:
        """Parse AI response with enhanced metadata"""
        
        # Use base parsing from Stage 1
        parsed = self._parse_simple_response(text)
        
        # Add RAG-enhanced metadata
        parsed.update({
            "context": context,
            "campaign": campaign,
            "has_rag_context": campaign is not None,
            "generation_method": "rag_enhanced" if campaign else "basic"
        })
        
        return parsed
    
    def _parse_simple_response(self, text: str) -> Dict[str, Any]:
        """Basic parsing from Stage 1 (backward compatibility)"""
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
        
        # Ensure we have content
        if not scene:
            scene = "You find yourself in an interesting situation that calls for action."
        
        if len(choices) < 3:
            default_choices = [
                "Look around carefully for clues",
                "Approach the situation cautiously", 
                "Wait and observe what happens"
            ]
            choices.extend(default_choices[:3-len(choices)])
        
        return {
            "scene": scene, 
            "choices": choices[:3]  # Limit to 3 choices
        }
    
    def _fallback_scenario(self, context: str, campaign: Optional[str]) -> Dict[str, Any]:
        """Enhanced fallback scenarios with campaign awareness"""
        
        # Base fallback scenarios from Stage 1
        base_scenarios = {
            "tavern": {
                "scene": "The tavern buzzes with quiet conversation. A hooded stranger sits alone in the corner, occasionally glancing your way. The bartender polishes glasses while keeping a watchful eye on all patrons.",
                "choices": [
                    "Approach the hooded stranger and strike up a conversation",
                    "Talk to the bartender about local rumors and news",
                    "Find a table and listen to the conversations around you"
                ]
            },
            "forest": {
                "scene": "Ancient trees tower above you as you follow a winding path. The canopy filters sunlight into dancing patterns, and you hear the distant sound of running water mixed with bird calls.",
                "choices": [
                    "Follow the sound of water to find a stream or river",
                    "Look for signs of other travelers on this path",
                    "Climb a tall tree to get your bearings"
                ]
            },
            "dungeon": {
                "scene": "Stone corridors stretch before you, lit by flickering torches. The air is damp and carries the scent of age and mystery. You hear the faint echo of dripping water somewhere ahead.",
                "choices": [
                    "Proceed carefully down the main corridor",
                    "Search the walls for secret passages or traps",
                    "Listen carefully for sounds of danger or treasure"
                ]
            },
            "town": {
                "scene": "The town square bustles with activity as merchants hawk their wares and townspeople go about their daily business. A notice board near the fountain catches your attention with several posted announcements.",
                "choices": [
                    "Read the notices on the board for potential opportunities",
                    "Visit the local merchant stalls to gather information",
                    "Ask townspeople about recent events or concerns"
                ]
            }
        }
        
        scenario = base_scenarios.get(context, base_scenarios["tavern"])
        
        # Add campaign context if available
        if campaign:
            scenario["scene"] = f"[{campaign}] " + scenario["scene"]
        
        # Add metadata
        scenario.update({
            "context": context,
            "campaign": campaign,
            "has_rag_context": False,
            "generation_method": "fallback"
        })
        
        return scenario
    
    def get_available_campaigns(self) -> List[str]:
        """Get list of available campaigns from document store"""
        try:
            campaigns = self.document_store.list_campaigns()
            return [c["name"] for c in campaigns]
        except Exception as e:
            print(f"⚠️ Failed to get campaigns: {e}")
            return []
    
    def add_campaign_content(self, campaign_name: str, content: str, content_type: str = "campaign") -> bool:
        """Add new campaign content to the RAG system"""
        try:
            metadata = {
                "name": campaign_name,
                "type": content_type,
                "source": "user_added"
            }
            
            return self.document_store.add_campaign_content(content, metadata)
            
        except Exception as e:
            print(f"❌ Failed to add campaign content: {e}")
            return False
    
    def search_campaign_info(self, query: str, campaign: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for specific campaign information"""
        try:
            # Enhance query with campaign name if provided
            if campaign:
                enhanced_query = f"{campaign} {query}"
            else:
                enhanced_query = query
            
            return self.document_store.search_with_metadata(enhanced_query, top_k=5)
            
        except Exception as e:
            print(f"⚠️ Campaign search failed: {e}")
            return []
    
    def get_rag_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        return self.document_store.get_stats()