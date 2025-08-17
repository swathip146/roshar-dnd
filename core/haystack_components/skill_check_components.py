"""
Skill Check Haystack Components
Wraps existing D&D agents as Haystack components for skill check pipeline
"""

from typing import Dict, Any, Optional, List
import uuid
import time
from haystack import component

# Import from agent_framework
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.messaging import AgentMessage, MessageType


@component
class RuleEnforcementComponent:
    """Haystack wrapper for Rule Enforcement Agent"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        validation_result=Dict[str, Any],
        requires_check=bool,
        skill=Optional[str],
        dc=Optional[int],
        success=bool
    )
    def run(self, correlation_id: str, entities: Dict[str, Any], utterance: str, **kwargs) -> Dict[str, Any]:
        """Execute rule validation through orchestrator"""
        try:
            # Determine what kind of check is needed
            kind = entities.get("skill", "general")
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="rule_enforcement",
                message_type=MessageType.REQUEST,
                action="check_rule",
                data={
                    "kind": kind,
                    "query": utterance,
                    "entities": entities,
                    **kwargs
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 5.0)
            
            # Extract rule validation information
            requires_check = result.get("requires_check", True)
            skill = result.get("skill", kind)
            dc = result.get("dc", 15)  # Default DC
            
            return {
                "validation_result": result,
                "requires_check": requires_check,
                "skill": skill,
                "dc": dc,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "validation_result": {"error": str(e)},
                "requires_check": False,
                "skill": None,
                "dc": None,
                "success": False
            }

    def _wait_for_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for response from message bus"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                        
            except Exception:
                pass
            
            time.sleep(0.1)
        
        return {"success": False, "error": "Response timeout"}


@component
class GameEngineComponent:
    """Haystack wrapper for Game Engine Agent (supports both regular and enhanced)"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
        # Check if we have an enhanced game engine
        self.enhanced_engine = getattr(agent_orchestrator, 'enhanced_game_engine_agent', None)
    
    @component.output_types(
        character_data=Dict[str, Any],
        success=bool,
        modifiers=Dict[str, Any],
        proficiencies=Dict[str, Any],
        conditions=List[str],
        advantage=bool,
        disadvantage=bool
    )
    def run(self, correlation_id: str, actor: Dict[str, Any], request_type: str = "character.ref.request"):
        """Get character reference data"""
        try:
            actor_name = actor.get("name", "unknown")
            
            # Prefer enhanced game engine if available
            target_agent = "enhanced_game_engine" if self.enhanced_engine else "game_engine"
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id=target_agent,
                message_type=MessageType.REQUEST,
                action="get_character_data",
                data={
                    "actor": actor_name,
                    "request_type": request_type,
                    "correlation_id": correlation_id
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 5.0)
            
            # Extract character information
            character_data = result.get("character_data", {})
            modifiers = character_data.get("modifiers", {})
            proficiencies = character_data.get("proficiencies", {})
            conditions = character_data.get("conditions", [])
            
            # Determine advantage/disadvantage from conditions
            advantage = "advantage" in conditions or "blessed" in conditions
            disadvantage = "disadvantage" in conditions or "cursed" in conditions
            
            return {
                "character_data": result,
                "success": result.get("success", True),
                "modifiers": modifiers,
                "proficiencies": proficiencies,
                "conditions": conditions,
                "advantage": advantage,
                "disadvantage": disadvantage
            }
            
        except Exception as e:
            return {
                "character_data": {"error": str(e)},
                "success": False,
                "modifiers": {},
                "proficiencies": {},
                "conditions": [],
                "advantage": False,
                "disadvantage": False
            }

    def _wait_for_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for response from message bus"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                        
            except Exception:
                pass
            
            time.sleep(0.1)
        
        return {"success": False, "error": "Response timeout"}


@component
class DiceSystemComponent:
    """Haystack wrapper for Dice System Agent"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
        
    @component.output_types(
        roll_result=Dict[str, Any],
        total=int,
        breakdown=List[int],
        success=bool
    )
    def run(self, correlation_id: str, expr: str = "1d20", 
            advantage: bool = False, disadvantage: bool = False):
        """Execute dice roll"""
        try:
            # Adjust expression for advantage/disadvantage
            if advantage and not disadvantage:
                expr = f"2d20kh1"  # Keep highest
            elif disadvantage and not advantage:
                expr = f"2d20kl1"  # Keep lowest
            elif not expr or expr == "1d20":
                expr = "1d20"
                
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="dice_system",
                message_type=MessageType.REQUEST,
                action="roll_dice",
                data={
                    "expr": expr,
                    "advantage": advantage,
                    "disadvantage": disadvantage,
                    "context": "skill_check"
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 5.0)
            
            # Extract dice roll information
            roll_result = result.get("result", {})
            total = roll_result.get("total", 0)
            breakdown = roll_result.get("breakdown", [total])
            
            return {
                "roll_result": result,
                "total": total,
                "breakdown": breakdown,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "roll_result": {"error": str(e)},
                "total": 0,
                "breakdown": [],
                "success": False
            }

    def _wait_for_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for response from message bus"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                        
            except Exception:
                pass
            
            time.sleep(0.1)
        
        return {"success": False, "error": "Response timeout"}


@component
class FinalResultComponent:
    """Calculate final skill check result"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        final_result=Dict[str, Any],
        success=bool
    )
    def run(self, correlation_id: str, roll_total: int, modifiers: Dict[str, Any], 
            skill: Optional[str], dc: Optional[int]):
        """Calculate final skill check total and success"""
        try:
            # Get skill modifier
            skill_mod = 0
            if skill and skill in modifiers:
                skill_mod = modifiers[skill]
            elif "ability_modifiers" in modifiers and skill:
                # Map skills to abilities
                skill_ability_map = {
                    "acrobatics": "dexterity",
                    "athletics": "strength", 
                    "perception": "wisdom",
                    "investigation": "intelligence",
                    "insight": "wisdom",
                    "persuasion": "charisma",
                    "deception": "charisma",
                    "intimidation": "charisma",
                    "stealth": "dexterity"
                }
                ability = skill_ability_map.get(skill, "dexterity")
                skill_mod = modifiers["ability_modifiers"].get(ability, 0)
            
            # Calculate total
            total = roll_total + skill_mod
            
            # Determine success
            success = total >= dc if dc else True
            
            final_result = {
                "roll": roll_total,
                "modifier": skill_mod,
                "total": total,
                "dc": dc,
                "success": success,
                "skill": skill,
                "timestamp": time.time(),
                "correlation_id": correlation_id
            }
            
            return {
                "final_result": final_result,
                "success": True
            }
            
        except Exception as e:
            return {
                "final_result": {"error": str(e)},
                "success": False
            }

    def _wait_for_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for response from message bus"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                history = self.orchestrator.message_bus.get_message_history(limit=50)
                
                for msg in reversed(history):
                    if (msg.get("response_to") == message_id and
                        msg.get("message_type") == "response"):
                        return msg.get("data", {})
                        
            except Exception:
                pass
            
            time.sleep(0.1)
        
        return {"success": False, "error": "Response timeout"}


@component  
class StateApplierComponent:
    """Apply skill check result to game state"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        applied_result=Dict[str, Any],
        success=bool
    )
    def run(self, correlation_id: str, final_result: Dict[str, Any], actor: Dict[str, Any]):
        """Apply result to game engine"""
        try:
            actor_name = actor.get("name", "unknown")
            
            # Check for enhanced game engine
            enhanced_engine = getattr(self.orchestrator, 'enhanced_game_engine_agent', None)
            target_agent = "enhanced_game_engine" if enhanced_engine else "game_engine"
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id=target_agent,
                message_type=MessageType.REQUEST,
                action="apply_skill_check_result",
                data={
                    "event": "skill_check.resolved",
                    "payload": {
                        **final_result,
                        "actor": actor_name
                    },
                    "correlation_id": correlation_id
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            apply_result = self._wait_for_response(message.id, 5.0)
            
            # Format final response
            applied_result = {
                "type": "skill.check.result",
                "data": final_result,
                "event_id": apply_result.get("event_id"),
                "timestamp": time.time(),
                "applied": apply_result.get("success", True)
            }
            
            return {
                "applied_result": applied_result,
                "success": apply_result.get("success", True)
            }
            
        except Exception as e:
            return {
                "applied_result": {"error": str(e)},
                "success": False
            }