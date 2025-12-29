"""
Haystack Agents Framework for D&D Game
AI-driven creative agents following Haystack patterns
"""

# Import factory functions instead of classes for Haystack Agents
from .scenario_generator_agent import (
    create_scenario_generator_agent,
    create_fallback_scenario,
    create_scenario_agent_for_orchestrator
)
from .rag_retriever_agent import create_rag_retriever_agent_simplified
from .npc_controller_agent import create_npc_controller_agent
from .main_interface_agent_fixed import create_fixed_interface_agent

__all__ = [
    # Factory functions for Haystack Agents
    "create_scenario_generator_agent",
    "create_fallback_scenario",
    "create_scenario_agent_for_orchestrator",
    "create_rag_retriever_agent_simplified",
    "create_npc_controller_agent",
    "create_fixed_interface_agent"
]