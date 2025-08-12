"""
NPC Controller for DM Assistant
Manages NPC behavior and decision-making using RAG and rule-based systems
"""
import random
from typing import Dict, List, Any, Optional

from agent_framework import BaseAgent, MessageType, AgentMessage
from haystack_pipeline_agent import HaystackPipelineAgent


class NPCControllerAgent(BaseAgent):
    """NPC Controller as an agent that manages NPC behavior and decisions"""
    
    def __init__(self, haystack_agent: Optional[HaystackPipelineAgent] = None, mode: str = "hybrid"):
        super().__init__("npc_controller", "NPCController")
        self.haystack_agent = haystack_agent
        self.mode = mode  # "haystack", "rule_based", or "hybrid"
    
    def _setup_handlers(self):
        """Setup message handlers for NPC controller"""
        self.register_handler("make_decisions", self._handle_make_decisions)
        self.register_handler("decide_for_npc", self._handle_decide_for_npc)
        self.register_handler("get_npc_status", self._handle_get_npc_status)
    
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
            "mode": self.mode,
            "haystack_available": self.haystack_agent is not None,
            "agent_type": self.agent_type
        }
    
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
    
    def _make_npc_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a decision for a single NPC"""
        # Check if NPC is marked as simple/rule-based only
        if npc.get("type") == "simple":
            return self._rule_based_decision(npc, game_state)
        
        # Use appropriate decision-making method based on mode
        if self.mode == "rule_based":
            return self._rule_based_decision(npc, game_state)
        elif self.mode == "haystack" and self.haystack_agent:
            return self._haystack_based_decision(npc, game_state)
        elif self.mode == "hybrid":
            # Try Haystack first, fall back to rule-based
            if self.haystack_agent:
                decision = self._haystack_based_decision(npc, game_state)
                if decision:
                    return decision
            return self._rule_based_decision(npc, game_state)
        else:
            return self._rule_based_decision(npc, game_state)
    
    def _haystack_based_decision(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make NPC decision using Haystack system"""
        prompt = self._build_prompt_for_npc(npc, game_state)
        
        try:
            response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
                "query": prompt,
                "npc_context": str(npc),
                "game_state": str(game_state)
            }, timeout=15.0)
            
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
    
    def process_tick(self):
        """Process NPC controller tick - mostly reactive, no regular processing needed"""
        pass


class NPCController:
    """Traditional NPCController class for backward compatibility"""
    
    def __init__(self, haystack_agent: Optional[HaystackPipelineAgent] = None, mode: str = "hybrid"):
        self.haystack_agent = haystack_agent
        self.mode = mode
    
    def decide(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Make decisions for all NPCs"""
        actions = []
        
        for npc_name, npc in game_state.get("npcs", {}).items():
            # Normalize NPC structure
            npc_obj = npc if isinstance(npc, dict) else {"name": npc}
            
            if npc_obj.get("type") == "simple":
                action = self._rule_based(npc_obj, game_state)
                if action:
                    actions.append(action)
            else:
                if self.mode in ("haystack", "hybrid") and self.haystack_agent:
                    prompt = self._build_prompt_for_npc(npc_obj, game_state)
                    try:
                        response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query_npc", {
                            "query": prompt,
                            "npc_context": str(npc_obj),
                            "game_state": str(game_state)
                        }, timeout=15.0)
                        
                        if response and response.get("success"):
                            result = response.get("result", {})
                            answer = result.get("answer", "")
                            
                            # Try to parse the response
                            if "to " in answer:
                                to_idx = answer.index("to ")
                                dest = answer[to_idx + 3:].split()[0]
                                actions.append({
                                    "actor": npc_name,
                                    "type": "move",
                                    "args": {"to": dest}
                                })
                        else:
                            # Fallback to rule-based
                            action = self._rule_based(npc_obj, game_state)
                            if action:
                                actions.append(action)
                    except Exception:
                        # Degrade to rule-based
                        action = self._rule_based(npc_obj, game_state)
                        if action:
                            actions.append(action)
        
        return actions
    
    def _rule_based(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Rule-based NPC decision making"""
        # Example priorities: flee if HP low, attack or patrol
        hp = npc.get("hp", 9999)
        max_hp = npc.get("max_hp", hp)
        
        if max_hp and hp < max(1, max_hp * 0.25):
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": npc.get("flee_to", "safe_spot")}
            }
        
        # If player in same location, choose to approach
        players = game_state.get("players", {})
        for player_name, player_data in players.items():
            if player_data.get("location") == npc.get("location"):
                return {
                    "actor": npc.get("name"),
                    "type": "raw_event",
                    "args": {"text": f"{npc.get('name')} engages {player_name}."}
                }
        
        # Else random patrol
        locations = game_state.get("world", {}).get("locations", [])
        if locations:
            return {
                "actor": npc.get("name"),
                "type": "move",
                "args": {"to": random.choice(locations)}
            }
        
        return None
    
    def _build_prompt_for_npc(self, npc: Dict[str, Any], game_state: Dict[str, Any]) -> str:
        """Build prompt for NPC decision making"""
        parts = [
            f"NPC: {npc.get('name')}",
            f"Role: {npc.get('role', 'unknown')}",
            f"HP: {npc.get('hp', '?')}"
        ]
        parts.append(f"Location: {npc.get('location', '?')}")
        parts.append("Recent events: " + ", ".join(game_state.get('session', {}).get('events', [])[-4:]))
        parts.append("What should this NPC do next? Be concise and return a tiny JSON-like answer with move_to if moving.")
        return "\n".join(parts)