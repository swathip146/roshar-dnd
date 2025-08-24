"""
Context Broker - Decides when to query RAG/Rules based on request context
Enriches requests with relevant context from RAG and memory systems
Updated to support shared DTO contract for predictable RAG assessment
"""

from typing import Dict, Any, Optional, List
import logging
from shared_contract import RequestDTO

# Configuration constants
DEFAULT_THRESH = {"lore": 0.35, "rules": 0.35, "world": 0.25}

class ContextBroker:
    """
    Context Broker for enriching requests with relevant context
    Decides when to query RAG/Rules based on request patterns
    """
    
    def __init__(self, rag_retriever=None, memory_manager=None):
        self.rag_retriever = rag_retriever
        self.memory_manager = memory_manager
        self.logger = logging.getLogger(__name__)
        
        # Context enrichment rules - enhanced for better matching
        self.rag_triggers = {
            "lore": [
                "history", "legend", "lore", "story", "past", "ancient", "origin",
                "tell me about", "who are", "what is", "information about", "know about",
                "alethi", "veden", "roshar", "shardbearer", "knight radiant", "herald",
                "spren", "vorin", "parshendi", "listener", "kaladin", "shallan", "dalinar"
            ],
            "rules": ["spell", "magic", "cast", "ability", "rule", "mechanic", "how does", "what happens if"],
            "monsters": ["creature", "monster", "beast", "dragon", "demon", "undead", "stats"],
            "locations": ["place", "location", "city", "dungeon", "area", "region", "where is"],
            "items": ["item", "weapon", "armor", "artifact", "treasure", "equipment", "gear"]
        }
        
        print("🧠 Context Broker initialized")
        
    def enrich_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich request with relevant context from RAG and memory
        
        Args:
            request: Original request dictionary
            
        Returns:
            Enriched request with additional context
        """
        # Defensive programming - handle None request
        if request is None:
            self.logger.warning("Received None request for context enrichment")
            return {}
            
        enriched_request = request.copy()
        
        try:
            # Determine if RAG lookup is needed
            rag_assessment = self._assess_rag_need(request)
            
            if rag_assessment["needed"]:
                rag_context = self._get_rag_context(request, rag_assessment)
                enriched_request["rag_context"] = rag_context
                enriched_request["rag_type"] = rag_assessment["type"]
                
            # Add memory context if available
            memory_context = self._get_memory_context(request)
            if memory_context:
                enriched_request["memory_context"] = memory_context
                
            # Add environmental context
            env_context = self._get_environmental_context(request)
            enriched_request["environmental_context"] = env_context
            
            # Mark as enriched
            enriched_request["context_enriched"] = True
            enriched_request["enrichment_timestamp"] = self._get_timestamp()
            
            self.logger.debug(f"Enriched request with RAG: {rag_assessment['needed']}")
            
        except Exception as e:
            self.logger.error(f"Context enrichment failed: {e}")
            self.logger.error(f"Request type: {type(request)}")
            self.logger.error(f"Request content: {request}")
            # Return original request on failure
            enriched_request = request.copy() if request is not None else {}
            enriched_request["context_enrichment_failed"] = True
            
        return enriched_request
    
    def _assess_rag_need(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Determine if request needs RAG document lookup"""
        
        # Defensive programming - handle None request
        if request is None:
            return {
                "needed": False,
                "type": None,
                "confidence": 0.0,
                "triggers": [],
                "query": ""
            }
        
        # Extract text content from request
        text_content = self._extract_text_content(request)
        text_lower = text_content.lower()
        
        # Check for RAG triggers with case-insensitive matching
        for context_type, triggers in self.rag_triggers.items():
            matched_triggers = []
            for trigger in triggers:
                if trigger.lower() in text_lower:
                    matched_triggers.append(trigger)
            
            if matched_triggers:
                # More generous confidence scaling
                confidence = min(0.9, len(matched_triggers) * 0.3 + 0.3)  # Base confidence of 0.3
                return {
                    "needed": True,
                    "type": context_type,
                    "confidence": confidence,
                    "triggers": matched_triggers,
                    "query": self._build_rag_query(text_content, context_type)
                }
        
        # Check request type patterns
        request_type = request.get("type", "")
        if not request_type:
            request_type = request.get("request_type", "")
        type_patterns = {
            "scenario": "lore",
            "npc_interaction": "lore", 
            "spell_lookup": "rules",
            "monster_encounter": "monsters"
        }
        
        if request_type in type_patterns:
            return {
                "needed": True,
                "type": type_patterns[request_type],
                "confidence": 0.6,
                "triggers": [request_type],
                "query": text_content
            }
        
        # Enhanced environment-based triggering
        context = request.get("context", {}) if request else {}
        if context:
            environment = context.get("environment", {})
            location = context.get("location", "").lower()
            
            # Location-based RAG triggers
            if any(loc in location for loc in ["library", "archive", "study", "temple", "ruins"]):
                return {
                    "needed": True,
                    "type": "lore",
                    "confidence": 0.7,
                    "triggers": ["location_context"],
                    "query": self._build_rag_query(text_content, "lore")
                }
            
            # Environment-based triggers
            if environment.get("type") in ["archive", "library", "study", "magical"]:
                return {
                    "needed": True,
                    "type": "lore",
                    "confidence": 0.7,
                    "triggers": ["environment_context"],
                    "query": self._build_rag_query(text_content, "lore")
                }
        
        return {
            "needed": False,
            "type": None,
            "confidence": 0.0,
            "triggers": [],
            "query": ""
        }
    
    def _extract_text_content(self, request: Dict[str, Any]) -> str:
        """Extract text content from request for analysis"""
        
        # Defensive programming - handle None request
        if request is None:
            return ""
            
        content_parts = []
        
        # Extract from various request fields
        if "action" in request:
            content_parts.append(request["action"])
            
        if "player_input" in request:
            content_parts.append(request["player_input"])
            
        if "data" in request and isinstance(request["data"], dict):
            for key, value in request["data"].items():
                if isinstance(value, str):
                    content_parts.append(value)
                    
        # Extract from context
        if "context" in request and isinstance(request["context"], dict):
            for key, value in request["context"].items():
                if isinstance(value, str):
                    content_parts.append(value)
        
        return " ".join(content_parts)
    
    def _build_rag_query(self, text_content: str, context_type: str) -> str:
        """Build optimized query for RAG retrieval"""
        
        # Extract key terms based on context type
        if context_type == "lore":
            # Focus on names, places, events
            query = self._extract_key_terms(text_content, ["history", "legend", "ancient"])
        elif context_type == "rules":
            # Focus on game mechanics
            query = self._extract_key_terms(text_content, ["spell", "ability", "rule"])
        elif context_type == "monsters":
            # Focus on creature names and types
            query = self._extract_key_terms(text_content, ["creature", "monster", "beast"])
        else:
            # General query
            query = text_content[:100]  # Truncate long queries
            
        return query
    
    def _extract_key_terms(self, text: str, focus_terms: List[str]) -> str:
        """Extract key terms for targeted queries"""
        words = text.lower().split()
        
        # Find focus terms and surrounding context
        key_phrases = []
        for i, word in enumerate(words):
            if any(term in word for term in focus_terms):
                # Extract 3 words before and after
                start = max(0, i - 3)
                end = min(len(words), i + 4)
                phrase = " ".join(words[start:end])
                key_phrases.append(phrase)
        
        if key_phrases:
            return " ".join(key_phrases)
        else:
            # Fallback to first 50 characters
            return text[:50]
    
    def _build_rag_filters(self, request: Dict[str, Any], context_type: str) -> Dict[str, Any]:
        """Build contextual filters for RAG retrieval based on request context"""
        
        # Start with base filters
        filters = {}
        
        # Add context-type specific filters
        if context_type == "lore":
            filters["document_type"] = ["lore", "history", "background"]
            filters["content_category"] = ["world_building", "narrative", "story"]
        elif context_type == "rules":
            filters["document_type"] = ["rules", "mechanics", "system"]
            filters["content_category"] = ["game_rules", "mechanics", "abilities"]
        elif context_type == "monsters":
            filters["document_type"] = ["bestiary", "monsters", "creatures"]
            filters["content_category"] = ["creatures", "combat", "stats"]
        elif context_type == "locations":
            filters["document_type"] = ["locations", "places", "geography"]
            filters["content_category"] = ["world_geography", "locations"]
        elif context_type == "items":
            filters["document_type"] = ["items", "equipment", "artifacts"]
            filters["content_category"] = ["equipment", "treasure", "items"]
        
        # Add environmental context filters
        if request and isinstance(request, dict):
            context = request.get("context", {})
            if context:
                # Location-based filtering
                location = context.get("location", "").lower()
                if location:
                    filters["location_context"] = location
                
                # Situation-based filtering
                if context.get("combat"):
                    filters["situation"] = "combat"
                elif context.get("social"):
                    filters["situation"] = "social"
                
                # Difficulty-based filtering
                difficulty = context.get("difficulty")
                if difficulty:
                    filters["difficulty_level"] = difficulty
        
        return filters
    
    def _get_rag_context(self, request: Dict[str, Any], rag_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Get RAG context from retriever using contextual filters"""
        
        if not self.rag_retriever:
            return {"error": "No RAG retriever available"}
            
        try:
            query = rag_assessment["query"]
            context_type = rag_assessment["type"]
            
            # Build contextual filters for better retrieval
            filters = self._build_rag_filters(request, context_type)
            
            # Prepare DTO-compatible retrieval request
            retrieval_request = {
                "query": query,
                "type": context_type,
                "filters": filters,
                "confidence_threshold": rag_assessment.get("confidence", 0.5),
                "max_documents": 5,
                "include_metadata": True
            }
            
            # Use RAG retriever with enhanced filtering
            # This would connect to the actual RAG agent
            retrieved_context = {
                "query": query,
                "type": context_type,
                "filters": filters,
                "documents": [],  # Would be populated by actual retriever
                "summary": f"Context for {context_type} query: {query[:50]}...",
                "confidence": rag_assessment["confidence"],
                "retrieval_request": retrieval_request
            }
            
            self.logger.debug(f"RAG context built with filters: {filters}")
            
            return retrieved_context
            
        except Exception as e:
            self.logger.error(f"RAG retrieval failed: {e}")
            return {"error": str(e), "query": rag_assessment.get("query", ""), "type": rag_assessment.get("type", "")}
    
    def _get_memory_context(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get relevant memory context"""
        
        if not self.memory_manager or request is None:
            return None
            
        try:
            # Extract character/session information for memory lookup
            character_id = request.get("actor", request.get("character_id"))
            session_id = request.get("session_id")
            
            memory_context = {
                "character_id": character_id,
                "session_id": session_id,
                "recent_actions": [],  # Would be populated by memory manager
                "significant_events": [],  # Would be populated by memory manager
                "context_available": False
            }
            
            return memory_context
            
        except Exception as e:
            self.logger.error(f"Memory context retrieval failed: {e}")
            return None
    
    def _get_environmental_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Get environmental/situational context"""
        
        # Defensive programming - handle None request
        if request is None:
            return {
                "location": "unknown",
                "environment": {},
                "time_pressure": False,
                "combat_active": False,
                "social_situation": False,
                "difficulty_context": "medium"
            }
        
        # Extract location and environmental factors
        context = request.get("context", {})
        if context is None:
            context = {}
        location = context.get("location", "unknown")
        environment = context.get("environment", {})
        
        # Enhance with derived context
        environmental_context = {
            "location": location,
            "environment": environment,
            "time_pressure": context.get("time_pressure", False),
            "combat_active": context.get("combat", False),
            "social_situation": context.get("social", False),
            "difficulty_context": context.get("difficulty", "medium")
        }
        
        # Add location-based context hints
        location_lower = location.lower()
        if any(term in location_lower for term in ["library", "archive", "study"]):
            environmental_context["research_available"] = True
        if any(term in location_lower for term in ["tavern", "inn", "social"]):
            environmental_context["social_opportunities"] = True
        if any(term in location_lower for term in ["dungeon", "cave", "dangerous"]):
            environmental_context["danger_level"] = "high"
            
        return environmental_context
    
    def _get_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()


# Factory function for easy integration
def create_context_broker(rag_retriever=None, memory_manager=None) -> ContextBroker:
    """Factory function to create configured context broker"""
    return ContextBroker(rag_retriever, memory_manager)


# Example usage and testing
if __name__ == "__main__":
    # Create context broker
    broker = create_context_broker()
    
    # Test context enrichment
    test_requests = [
        {
            "type": "scenario",
            "action": "I want to research the history of the ancient dragon kings",
            "context": {"location": "Ancient Library", "difficulty": "medium"}
        },
        {
            "type": "skill_check", 
            "action": "I cast fireball at the goblins",
            "actor": "player",
            "context": {"combat": True, "enemies": ["goblins"]}
        },
        {
            "type": "general",
            "player_input": "I look around the tavern",
            "context": {"location": "Tavern", "social": True}
        }
    ]
    
    print("=== Context Broker Tests ===")
    
    for i, request in enumerate(test_requests):
        print(f"\nTest {i+1}: {request['action'] if 'action' in request else request.get('player_input', 'Unknown')}")
        
        enriched = broker.enrich_context(request)
        
        print(f"  RAG Context: {'Yes' if enriched.get('rag_context') else 'No'}")
        print(f"  Memory Context: {'Yes' if enriched.get('memory_context') else 'No'}")
        print(f"  Environmental: {enriched.get('environmental_context', {}).get('location', 'Unknown')}")
        
        if enriched.get('rag_context'):
            print(f"  RAG Type: {enriched.get('rag_type')}")