"""
Haystack Agents Framework for D&D Game
AI-driven creative agents following Haystack patterns
"""

import os

# Load embedding models from the LOCAL CACHE without contacting the Hugging Face hub.
#
# THIS MUST BE THE FIRST THING THIS PACKAGE DOES. `huggingface_hub` computes
#     HF_HUB_OFFLINE = _is_true(os.environ.get("HF_HUB_OFFLINE") or
#                               os.environ.get("TRANSFORMERS_OFFLINE"))
# once, at ITS import time, into a module constant. The agent imports below pull it in
# transitively, so anything that sets the variable later — including
# `agents/dm_tools.py`'s own module body — is already too late. Traced by watching
# `huggingface_hub.constants.HF_HUB_OFFLINE` stay False while `os.environ` said "1".
#
# `BAAI/bge-large-en-v1.5` is already cached under ~/.cache/huggingface/hub, but
# sentence-transformers still checks the hub for updates unless told not to, and on a
# network that proxies egress that check fails with `ProxyError 403 Forbidden`. The
# visible symptom was `search_lore` returning
# `{"passages": [], "error": "403 Forbidden"}` for EVERY query — so a live Suite B run
# recorded the tool as reaching nothing, and I initially mislabelled that a prompt gap.
# With the flag set the embedder yields a 1024-dim vector from cache and the same query
# returns 4 real passages.
#
# The scripts under `scripts/` all set this flag themselves, which is exactly why the
# tool looked healthy there while every other caller silently got zero lore.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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