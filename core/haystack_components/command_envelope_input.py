"""
CommandEnvelope Input Component for Haystack Pipelines
Separate module to avoid circular imports
"""

from typing import Dict, Any
from haystack import component
from ..command_envelope import CommandEnvelope


@component
class CommandEnvelopeInput:
    """
    Haystack component to handle CommandEnvelope inputs
    
    This component serves as the entry point for Haystack pipelines,
    converting CommandEnvelope data into individual pipeline inputs.
    """
    
    @component.output_types(
        command_envelope=CommandEnvelope,
        correlation_id=str,
        actor=Dict[str, Any],
        intent=str,
        entities=Dict[str, Any],
        utterance=str,
        context=Dict[str, Any],
        parameters=Dict[str, Any],
        metadata=Dict[str, Any]
    )
    def run(
        self, 
        command_envelope: CommandEnvelope, 
        correlation_id: str, 
        actor: Dict[str, Any], 
        intent: str, 
        entities: Dict[str, Any], 
        utterance: str,
        context: Dict[str, Any],
        parameters: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process CommandEnvelope and output individual components
        
        Returns:
            Dict containing all the individual components from the envelope
        """
        return {
            "command_envelope": command_envelope,
            "correlation_id": correlation_id,
            "actor": actor,
            "intent": intent,
            "entities": entities,
            "utterance": utterance,
            "context": context,
            "parameters": parameters,
            "metadata": metadata
        }