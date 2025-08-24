"""
Phase 4: Simplified Unified Pipeline Architecture
Demonstrates the concept without complex agent dependencies
"""

import sys
import os
from typing import Dict, Any, List, Optional

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared_contract import RequestDTO, normalize_incoming, validate_scenario, repair_scenario, minimal_fallback


class SimpleUnifiedPipeline:
    """
    Simplified Phase 4 unified pipeline demonstrating the architecture concept
    """
    
    def __init__(self):
        self.phase = "4_unified_pipeline_simple"
        self.components = [
            "normalizer", "router", "rag_gate", 
            "scenario_handler", "npc_handler", "rules_handler", "meta_handler"
        ]
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the simplified unified pipeline
        
        Args:
            request: Raw incoming request
            
        Returns:
            Processed response with route-specific handling
        """
        try:
            # Step 1: Normalize incoming request to DTO
            dto = self._normalize_step(request)
            
            # Step 2: Make routing decision
            dto = self._routing_step(dto)
            
            # Step 3: RAG gating
            dto = self._rag_gating_step(dto)
            
            # Step 4: Route-specific processing
            result = self._route_processing_step(dto)
            
            return {
                "success": True,
                "result": result,
                "pipeline_used": "unified_simple",
                "phase": self.phase
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fallback_used": True,
                "pipeline_used": "unified_simple",
                "phase": self.phase
            }
    
    def _normalize_step(self, request: Dict[str, Any]) -> RequestDTO:
        """Step 1: Normalize incoming request"""
        return normalize_incoming(request)
    
    def _routing_step(self, dto: RequestDTO) -> RequestDTO:
        """Step 2: Apply hard routing rules"""
        player_input = dto.get("player_input", "").lower()
        
        # Phase 2: Hard routing rules
        if any(keyword in player_input for keyword in ["rule", "rules", "how do", "spell", "mechanics"]):
            dto["route"] = "rules"
        elif any(keyword in player_input for keyword in ["talk to", "speak with", "ask", "tell"]):
            dto["route"] = "npc"
        elif any(keyword in player_input for keyword in ["save", "load", "inventory", "help", "quit"]):
            dto["route"] = "meta"
        else:
            dto["route"] = "scenario"
            
        return dto
    
    def _rag_gating_step(self, dto: RequestDTO) -> RequestDTO:
        """Step 3: Determine if RAG is needed"""
        player_input = dto.get("player_input", "").lower()
        
        # Phase 1: Permissive RAG gating
        rag_triggers = [
            "lore", "history", "legend", "ancient", "artifact", "dragon", 
            "magic", "spell", "enchant", "curse", "prophecy", "kingdom"
        ]
        
        rag_needed = any(trigger in player_input for trigger in rag_triggers)
        
        dto["rag"]["needed"] = rag_needed
        if rag_needed:
            dto["rag"]["query"] = player_input
            dto["rag"]["filters"] = {"type": "lore", "relevance": "high"}
            dto["rag"]["docs"] = []  # Would be populated by actual RAG
        
        return dto
    
    def _route_processing_step(self, dto: RequestDTO) -> Dict[str, Any]:
        """Step 4: Process based on route"""
        route = dto.get("route", "scenario")
        
        if route == "scenario":
            return self._scenario_handler(dto)
        elif route == "npc":
            return self._npc_handler(dto)
        elif route == "rules":
            return self._rules_handler(dto)
        elif route == "meta":
            return self._meta_handler(dto)
        else:
            return self._scenario_handler(dto)  # Default fallback
    
    def _scenario_handler(self, dto: RequestDTO) -> Dict[str, Any]:
        """Handle scenario generation with Phase 3 validation"""
        player_input = dto.get("player_input", "")
        context = dto.get("context", {})
        
        # Create scenario
        scenario = {
            "scene": f"As you {player_input.lower()}, the world responds around you.",
            "choices": [
                {
                    "id": "c1",
                    "title": "Proceed carefully",
                    "description": "Continue with caution",
                    "skill_hints": ["perception", "stealth"],
                    "suggested_dc": 12,
                    "combat_trigger": False
                },
                {
                    "id": "c2",
                    "title": "Act boldly", 
                    "description": "Take decisive action",
                    "skill_hints": ["athletics", "intimidation"],
                    "suggested_dc": 15,
                    "combat_trigger": False
                }
            ],
            "effects": {},
            "hooks": []
        }
        
        # Phase 3: Schema validation and repair
        errors = validate_scenario(scenario)
        if errors:
            scenario = repair_scenario(scenario, errors)
            dto["debug"]["scenario_repaired"] = True
            
            # Re-validate
            errors = validate_scenario(scenario)
            
        if errors:
            # Still invalid - use minimal fallback
            dto["debug"]["scenario_errors"] = errors
            dto["fallback"] = True
            scenario = minimal_fallback(dto)
        else:
            dto["fallback"] = False
            
        dto["scenario"] = scenario
        return {"dto_with_scenario": dto}
    
    def _npc_handler(self, dto: RequestDTO) -> Dict[str, Any]:
        """Handle NPC interactions"""
        player_input = dto.get("player_input", "")
        target = dto.get("target", "someone")
        
        dto["npc"] = {
            "response": f"The {target} responds: 'Greetings, traveler. {player_input}'"
        }
        
        return {"dto_with_npc": dto}
    
    def _rules_handler(self, dto: RequestDTO) -> Dict[str, Any]:
        """Handle rules lookup"""
        query = dto.get("player_input", "")
        
        dto["rules_response"] = {
            "query": query,
            "response": f"D&D 5e rules for: {query}",
            "source": "Basic Rules"
        }
        
        return {"dto_with_rules": dto}
    
    def _meta_handler(self, dto: RequestDTO) -> Dict[str, Any]:
        """Handle meta commands"""
        command = dto.get("player_input", "").lower()
        
        if "save" in command:
            response = "Game saved successfully"
        elif "load" in command:
            response = "Game loaded successfully"
        elif "inventory" in command:
            response = "Inventory: Sword, Health Potion, 50 gold"
        else:
            response = f"Command processed: {command}"
            
        dto["meta_response"] = {
            "command": command,
            "response": response
        }
        
        return {"dto_with_meta": dto}
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get pipeline information"""
        return {
            "type": "unified_pipeline_simple",
            "phase": "4",
            "components": self.components,
            "features": [
                "DTO normalization (Phase 0)",
                "Hard routing rules (Phase 2)", 
                "Permissive RAG gating (Phase 1)",
                "Schema validation (Phase 3)",
                "Route-specific processing"
            ],
            "architecture": "Single linear pipeline with conditional processing"
        }


# Factory function
def create_unified_pipeline() -> SimpleUnifiedPipeline:
    """Create unified pipeline"""
    return SimpleUnifiedPipeline()


# Test the pipeline
if __name__ == "__main__":
    pipeline = SimpleUnifiedPipeline()
    
    test_requests = [
        {
            "player_input": "I examine the ancient artifact",
            "context": {"location": "Temple", "difficulty": "medium"}
        },
        {
            "player_input": "I talk to the innkeeper about local rumors",
            "context": {"location": "Tavern"}
        },
        {
            "player_input": "How do skill checks work?",
            "context": {}
        },
        {
            "player_input": "save game",
            "context": {}
        }
    ]
    
    print("=" * 50)
    print("PHASE 4 UNIFIED PIPELINE TESTS")
    print("=" * 50)
    
    for i, request in enumerate(test_requests):
        print(f"\n--- Test {i+1}: {request['player_input']} ---")
        
        result = pipeline.run(request)
        
        print(f"Success: {result['success']}")
        
        if result["success"]:
            result_data = result["result"]
            
            # Show route taken
            if "dto_with_scenario" in result_data:
                dto = result_data["dto_with_scenario"]
                print(f"Route: {dto.get('route', 'unknown')}")
                print(f"RAG needed: {dto.get('rag', {}).get('needed', False)}")
                print(f"Scenario fallback: {dto.get('fallback', 'unknown')}")
                
            elif "dto_with_npc" in result_data:
                print(f"Route: npc")
                print(f"Response: {result_data['dto_with_npc']['npc']['response']}")
                
            elif "dto_with_rules" in result_data:
                print(f"Route: rules")
                print(f"Query: {result_data['dto_with_rules']['rules_response']['query']}")
                
            elif "dto_with_meta" in result_data:
                print(f"Route: meta")
                print(f"Response: {result_data['dto_with_meta']['meta_response']['response']}")
        else:
            print(f"Error: {result['error']}")
    
    # Show pipeline info
    print(f"\n--- Pipeline Info ---")
    info = pipeline.get_pipeline_info()
    print(f"Type: {info['type']}")
    print(f"Phase: {info['phase']}")
    print(f"Components: {', '.join(info['components'])}")
    print(f"Architecture: {info['architecture']}")
    print("\nFeatures:")
    for feature in info['features']:
        print(f"  - {feature}")