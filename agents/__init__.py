"""
Haystack Agents Framework for D&D Game
AI-driven creative agents following Haystack patterns
"""

from .base_agent import BaseDnDAgent

# Import factory functions instead of classes for Haystack Agents
from .scenario_generator_agent import (
    create_scenario_generator_agent,
    create_fallback_scenario,
    create_scenario_agent_for_orchestrator
)
from .rag_retriever_agent import create_rag_retriever_agent
from .npc_controller_agent import create_npc_controller_agent
from .main_interface_agent import create_main_interface_agent

__all__ = [
    "BaseDnDAgent",
    # Factory functions for Haystack Agents
    "create_scenario_generator_agent",
    "create_fallback_scenario",
    "create_scenario_agent_for_orchestrator",
    "create_rag_retriever_agent",
    "create_npc_controller_agent",
    "create_main_interface_agent"
]