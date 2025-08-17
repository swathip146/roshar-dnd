"""
Scenario Choice Haystack Components
Components for handling D&D scenario choices and consequences
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
class ScenarioValidatorComponent:
    """Validates scenario choices and determines if skill checks are needed"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        validation_result=Dict[str, Any],
        requires_skill_check=bool,
        choice_info=Dict[str, Any],
        success=bool
    )
    def run(self, correlation_id: str, entities: Dict[str, Any], 
            context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Validate scenario choice and determine if skill check is needed"""
        try:
            choice_id = entities.get("choice", 1)
            scenario_context = context.get("current_scenario", {})
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="rule_enforcement",
                message_type=MessageType.REQUEST,
                action="validate_choice",
                data={
                    "choice_id": choice_id,
                    "scenario_context": scenario_context,
                    "entities": entities,
                    **kwargs
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 5.0)
            
            # Extract validation information
            requires_skill_check = result.get("requires_skill_check", False)
            choice_info = result.get("choice_info", {})
            
            return {
                "validation_result": result,
                "requires_skill_check": requires_skill_check,
                "choice_info": choice_info,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "validation_result": {"error": str(e)},
                "requires_skill_check": False,
                "choice_info": {},
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
class RAGContextRetrieverComponent:
    """Retrieves relevant context using RAG for scenario enhancement"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        rag_context=List[str],
        context_documents=List[Dict[str, Any]],
        success=bool
    )
    def run(self, correlation_id: str, choice_info: Dict[str, Any], 
            utterance: str, **kwargs) -> Dict[str, Any]:
        """Retrieve RAG context for scenario enhancement"""
        try:
            # Create query for RAG system
            query = f"D&D scenario: {utterance} choice consequences"
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="haystack_pipeline",
                message_type=MessageType.REQUEST,
                action="query_rag",
                data={
                    "query": query,
                    "max_documents": 3,
                    "context": choice_info
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 8.0)
            
            # Extract RAG information
            rag_result = result.get("result", {})
            documents = rag_result.get("documents", [])
            context_strings = [doc.get("content", "") for doc in documents if doc.get("content")]
            
            return {
                "rag_context": context_strings,
                "context_documents": documents,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "rag_context": [],
                "context_documents": [],
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
class ScenarioGeneratorComponent:
    """Generate scenario consequences based on choice and context"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        scenario_result=Dict[str, Any],
        consequence_text=str,
        new_options=List[str],
        success=bool
    )
    def run(self, correlation_id: str, choice_info: Dict[str, Any],
            rag_context: List[str], skill_check_result: Optional[Dict[str, Any]] = None,
            **kwargs) -> Dict[str, Any]:
        """Generate consequence based on choice outcome"""
        try:
            # Determine consequence type
            if skill_check_result:
                outcome = "success" if skill_check_result.get("success") else "failure"
                consequence_type = "skill_check_consequence"
            else:
                outcome = "automatic_success"
                consequence_type = "choice_consequence"
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="scenario_generator",
                message_type=MessageType.REQUEST,
                action="generate_consequence",
                data={
                    "type": consequence_type,
                    "outcome": outcome,
                    "choice_info": choice_info,
                    "skill_result": skill_check_result,
                    "context": rag_context
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 15.0)
            
            # Extract scenario result
            scenario = result.get("scenario", {})
            consequence_text = scenario.get("consequence_text", "Choice processed successfully.")
            new_options = scenario.get("options", [])
            
            return {
                "scenario_result": result,
                "consequence_text": consequence_text,
                "new_options": new_options,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "scenario_result": {"error": str(e)},
                "consequence_text": f"Error generating consequence: {str(e)}",
                "new_options": [],
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
class ScenarioStateUpdaterComponent:
    """Updates game state with scenario results"""
    
    def __init__(self, agent_orchestrator):
        self.orchestrator = agent_orchestrator
    
    @component.output_types(
        updated_state=Dict[str, Any],
        success=bool
    )
    def run(self, correlation_id: str, scenario_result: Dict[str, Any],
            actor: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Update game state with scenario results"""
        try:
            actor_name = actor.get("name", "unknown")
            
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="haystack_pipeline",
                receiver_id="game_engine",
                message_type=MessageType.REQUEST,
                action="update_scenario_state",
                data={
                    "event": "scenario.choice.resolved",
                    "payload": {
                        "actor": actor_name,
                        "scenario_result": scenario_result,
                        "timestamp": time.time()
                    }
                },
                timestamp=time.time()
            )
            
            # Send message and wait for response
            self.orchestrator.message_bus.send_message(message)
            result = self._wait_for_response(message.id, 5.0)
            
            return {
                "updated_state": result,
                "success": result.get("success", True)
            }
            
        except Exception as e:
            return {
                "updated_state": {"error": str(e)},
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