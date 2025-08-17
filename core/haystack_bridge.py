"""
Haystack Bridge for D&D Assistant
Bridges CommandEnvelope system with Haystack pipelines
"""

from typing import Dict, Any, Optional
import uuid
import time
from haystack import Pipeline, component
from haystack.core.serialization import default_to_dict, default_from_dict

from .command_envelope import CommandEnvelope, CommandStatus, create_command_envelope
from .haystack_pipeline_registry import HaystackPipelineRegistry
# Import AgentMessage and MessageType inside functions to avoid circular imports


class HaystackOrchestrator:
    """
    Bridge between CommandEnvelope system and Haystack pipelines
    
    This class provides the integration layer that allows the existing D&D Assistant
    to leverage Haystack pipelines while maintaining backward compatibility with
    the current AgentOrchestrator system.
    """
    
    def __init__(self, agent_orchestrator, verbose: bool = False):
        """
        Initialize the Haystack bridge
        
        Args:
            agent_orchestrator: The existing AgentOrchestrator instance
            verbose: Whether to enable verbose logging
        """
        self.agent_orchestrator = agent_orchestrator
        self.verbose = verbose
        self.active_commands: Dict[str, CommandEnvelope] = {}
        
        # Initialize the pipeline registry
        try:
            self.pipeline_registry = HaystackPipelineRegistry(agent_orchestrator, verbose=verbose)
            if self.verbose:
                registry_status = self.pipeline_registry.get_registry_status()
                print(f"🚀 Haystack Pipeline Registry initialized with {registry_status['total_pipelines']} pipelines")
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize pipeline registry: {e}")
            self.pipeline_registry = None
    
    def register_pipeline(self, intent: str, pipeline: Pipeline, metadata: Optional[Dict[str, Any]] = None):
        """
        Register a Haystack pipeline for a specific intent
        
        Args:
            intent: The command intent (e.g., "SKILL_CHECK", "SCENARIO_CHOICE")
            pipeline: The Haystack pipeline to handle this intent
            metadata: Optional metadata about the pipeline
        """
        if self.pipeline_registry:
            self.pipeline_registry.register_pipeline(intent, pipeline, metadata)
            if self.verbose:
                print(f"🔧 Registered Haystack pipeline for intent: {intent}")
        else:
            if self.verbose:
                print(f"⚠️ Cannot register pipeline for {intent}: registry not available")
    
    def handle_command(self, envelope: CommandEnvelope) -> Dict[str, Any]:
        """
        Handle a command using either Haystack pipelines or fallback to legacy system
        
        Args:
            envelope: The command envelope to process
            
        Returns:
            Dict containing the result of command processing
        """
        try:
            # Mark command as processing
            envelope.mark_processing()
            self.active_commands[envelope.header.correlation_id] = envelope
            
            intent = envelope.header.intent
            
            if self.verbose:
                print(f"🎯 Processing command with intent: {intent}")
                print(f"📝 Correlation ID: {envelope.header.correlation_id}")
            
            # Check if we have a Haystack pipeline for this intent
            pipeline = None
            if self.pipeline_registry:
                pipeline = self.pipeline_registry.get_pipeline(intent)
            
            if pipeline:
                if self.verbose:
                    print(f"🚀 Using Haystack pipeline for {intent}")
                return self._execute_haystack_pipeline(envelope, pipeline)
            else:
                if self.verbose:
                    print(f"⤴️ Falling back to legacy system for {intent}")
                return self._execute_legacy_fallback(envelope)
                
        except Exception as e:
            error_msg = f"Error processing command: {str(e)}"
            envelope.mark_failed(error_msg)
            if self.verbose:
                print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        
        finally:
            # Clean up active command tracking
            if envelope.header.correlation_id in self.active_commands:
                del self.active_commands[envelope.header.correlation_id]
    
    def _execute_haystack_pipeline(self, envelope: CommandEnvelope, pipeline: Pipeline) -> Dict[str, Any]:
        """
        Execute a Haystack pipeline with the command envelope
        
        Args:
            envelope: The command envelope
            pipeline: The Haystack pipeline to execute
            
        Returns:
            Dict containing pipeline execution results
        """
        try:
            # Convert CommandEnvelope to Haystack pipeline inputs
            haystack_inputs = self._envelope_to_haystack_inputs(envelope)
            
            if self.verbose:
                print(f"🔄 Executing Haystack pipeline with inputs: {list(haystack_inputs.keys())}")
            
            # Execute the Haystack pipeline
            start_time = time.time()
            result = pipeline.run(haystack_inputs)
            execution_time = time.time() - start_time
            
            if self.verbose:
                print(f"✅ Pipeline executed in {execution_time:.2f}s")
            
            # Convert Haystack result back to standard format
            processed_result = self._process_haystack_result(result, envelope)
            
            # Mark command as completed
            envelope.mark_completed(processed_result)
            
            return processed_result
            
        except Exception as e:
            error_msg = f"Haystack pipeline execution failed: {str(e)}"
            envelope.mark_failed(error_msg)
            raise
    
    # # def _execute_legacy_fallback(self, envelope: CommandEnvelope) -> Dict[str, Any]:
    #     """
    #     Fallback to the existing AgentOrchestrator system
        
    #     Args:
    #         envelope: The command envelope
            
    #     Returns:
    #         Dict containing legacy system results
    #     """
    #     try:
    #         # Convert CommandEnvelope to legacy AgentMessage format
    #         legacy_message = self._envelope_to_legacy_message(envelope)
            
    #         if self.verbose:
    #             print(f"📤 Sending legacy message to agent: {legacy_message.receiver_id}")
            
    #         # Send through existing message bus
    #         self.agent_orchestrator.message_bus.send_message(legacy_message)
            
    #         # Wait for response (simplified - could be enhanced)
    #         response = self._wait_for_legacy_response(legacy_message.id, envelope.header.timeout_seconds)
            
    #         if response:
    #             envelope.mark_completed(response)
    #             return response
    #         else:
    #             error_msg = "No response from legacy system"
    #             envelope.mark_failed(error_msg)
    #             return {"success": False, "error": error_msg}
                
    #     except Exception as e:
    #         error_msg = f"Legacy fallback failed: {str(e)}"
    #         envelope.mark_failed(error_msg)
    #         return {"success": False, "error": error_msg}
    
    def _envelope_to_haystack_inputs(self, envelope: CommandEnvelope) -> Dict[str, Any]:
        """
        Convert CommandEnvelope to Haystack pipeline inputs
        
        Args:
            envelope: The command envelope
            
        Returns:
            Dict of inputs for Haystack pipeline
        """
        return {
            "command_envelope": envelope,
            "correlation_id": envelope.header.correlation_id,
            "actor": envelope.header.actor,
            "intent": envelope.header.intent,
            "entities": envelope.body.entities,
            "utterance": envelope.body.utterance,
            "context": envelope.body.context,
            "parameters": envelope.body.parameters,
            "metadata": envelope.body.metadata
        }
    
    # # def _envelope_to_legacy_message(self, envelope: CommandEnvelope):
    #     """
    #     Convert CommandEnvelope to legacy AgentMessage format
        
    #     Args:
    #         envelope: The command envelope
            
    #     Returns:
    #         AgentMessage for legacy system
    #     """
    #     # Import here to avoid circular imports
    #     from core.messaging import AgentMessage, MessageType
        
    #     # Determine target agent based on intent
    #     agent_mapping = {
    #         "SKILL_CHECK": "rule_enforcement",
    #         "SCENARIO_CHOICE": "scenario_generator",
    #         "RULE_QUERY": "rule_enforcement",
    #         "COMBAT_ACTION": "combat_engine",
    #         "LORE_LOOKUP": "haystack_pipeline"
    #     }
        
    #     target_agent = agent_mapping.get(envelope.header.intent, "haystack_pipeline")
        
    #     return AgentMessage(
    #         id=str(uuid.uuid4()),
    #         sender_id="haystack_orchestrator",
    #         receiver_id=target_agent,
    #         message_type=MessageType.REQUEST,
    #         action=envelope.header.intent.lower().replace("_", "."),
    #         data={
    #             "utterance": envelope.body.utterance,
    #             "entities": envelope.body.entities,
    #             "context": envelope.body.context,
    #             "correlation_id": envelope.header.correlation_id,
    #             "actor": envelope.header.actor
    #         },
    #         timestamp=time.time()
    #     )
    
    # # def _wait_for_legacy_response(self, message_id: str, timeout: float) -> Optional[Dict[str, Any]]:
    #     """
    #     Wait for a response from the legacy message bus system
        
    #     Args:
    #         message_id: The ID of the message we're waiting for a response to
    #         timeout: Maximum time to wait in seconds
            
    #     Returns:
    #         Response data or None if timeout
    #     """
    #     start_time = time.time()
        
    #     while time.time() - start_time < timeout:
    #         try:
    #             history = self.agent_orchestrator.message_bus.get_message_history(limit=50)
                
    #             for msg in reversed(history):
    #                 if (msg.get("response_to") == message_id and
    #                     msg.get("message_type") == "response"):
    #                     return msg.get("data", {})
                        
    #         except Exception as e:
    #             if self.verbose:
    #                 print(f"⚠️ Error checking legacy response: {e}")
            
    #         time.sleep(0.1)
        
    #     return None
    
    def _process_haystack_result(self, haystack_result: Dict[str, Any], envelope: CommandEnvelope) -> Dict[str, Any]:
        """
        Process and standardize Haystack pipeline results
        
        Args:
            haystack_result: Raw result from Haystack pipeline
            envelope: The original command envelope
            
        Returns:
            Standardized result dictionary
        """
        # Extract the main result from Haystack output
        # This will depend on the specific pipeline structure
        
        processed_result = {
            "success": True,
            "correlation_id": envelope.header.correlation_id,
            "intent": envelope.header.intent,
            "timestamp": time.time(),
            "execution_info": {
                "pipeline_used": True,
                "processing_time": time.time() - envelope.header.timestamp
            }
        }
        
        # Merge in the actual Haystack results
        if haystack_result:
            processed_result.update(haystack_result)
        
        return processed_result
    
    def get_active_commands(self) -> Dict[str, CommandEnvelope]:
        """Get currently active commands"""
        return self.active_commands.copy()
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about registered pipelines"""
        base_info = {
            "active_commands": len(self.active_commands),
            "registry_available": self.pipeline_registry is not None
        }
        
        if self.pipeline_registry:
            registry_info = self.pipeline_registry.get_pipeline_info()
            base_info.update(registry_info)
        else:
            base_info.update({
                "registered_pipelines": [],
                "pipeline_count": 0,
                "error": "Pipeline registry not available"
            })
        
        return base_info
    
    def test_pipeline(self, intent: str, test_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Test a specific pipeline
        
        Args:
            intent: The intent of the pipeline to test
            test_inputs: Optional test inputs
            
        Returns:
            Test results
        """
        if not self.pipeline_registry:
            return {
                "success": False,
                "error": "Pipeline registry not available",
                "intent": intent
            }
        
        return self.pipeline_registry.test_pipeline(intent, test_inputs)
    
    def get_registry_status(self) -> Dict[str, Any]:
        """
        Get registry status information
        
        Returns:
            Registry status dictionary
        """
        if not self.pipeline_registry:
            return {
                "available": False,
                "error": "Pipeline registry not initialized"
            }
        
        status = self.pipeline_registry.get_registry_status()
        status["available"] = True
        return status


# CommandEnvelopeInput moved to core.haystack_components.command_envelope_input
# to avoid circular imports