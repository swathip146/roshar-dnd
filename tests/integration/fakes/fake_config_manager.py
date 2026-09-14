"""
A `LLMConfigManager` that hands out scripted generators instead of network clients.

WHY THIS WORKS WITHOUT TOUCHING ANY AGENT
-----------------------------------------
Verified on `phase-0-fixes`: every LLM call in the app funnels through exactly one
factory —

    LLMConfigManager.create_generator(agent_name, response_schema=None)
        config/llm_config.py:388-412

with 13 call sites (scenario_generator_agent.py:757,957; npc_controller_agent.py:382;
main_interface_agent_fixed.py:449; rag_retriever_agent.py:322; npc_combat_ai.py:302;
pipeline_integration.py:295,334,351,368,375,1004).

And `config/llm_config.py:612` already exposes `set_global_config_manager()`. So a
subclass that overrides one method redirects every agent at once, with no production
edits.

SUBCLASSING RATHER THAN DUCK-TYPING IS DELIBERATE
-------------------------------------------------
Agents also read `manager.config.<agent>.model`, `.temperature` and friends. Inheriting
keeps all of that real, so a fake cannot drift away from the production object's shape
— exactly the decay that broke three of the four stale tests this suite replaces.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.llm_config import (
    AgentLLMConfig,
    LLMConfig,
    LLMConfigManager,
    LLMProvider,
    get_global_config_manager,
    set_global_config_manager,
)
from config.logging_config import get_logger

from .fake_generator import ScriptedChatGenerator

logger = get_logger(__name__)


def _offline_agent_config() -> AgentLLMConfig:
    """Config with real shape but no provider that could reach a network."""
    def cfg(temperature: float, max_tokens: int) -> LLMConfig:
        return LLMConfig(
            provider=LLMProvider.GEMINI,   # shape only; no client is ever built
            model="fake-model",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return AgentLLMConfig(
        scenario_generator=cfg(0.8, 8000),
        rag_retriever=cfg(0.3, 1500),
        npc_controller=cfg(0.9, 2000),
        main_interface=cfg(0.5, 2000),
        default_fallback=cfg(0.7, 2000),
    )


class ScriptedConfigManager(LLMConfigManager):
    """Hands every agent a `ScriptedChatGenerator` driven by a policy.

    Args:
        policy: default policy for any agent without a specific one.
        policies: per-agent overrides, keyed by the `agent_name` the production code
            passes to `create_generator` ("scenario_generator", "main_interface",
            "npc_controller", "rag_retriever", "npc_combat_ai", "combat_init",
            "combat_narrative").
    """

    def __init__(self, policy: Any = None, policies: Optional[Dict[str, Any]] = None):
        # Skip LLMConfigManager._validate_config's provider/key checks by setting
        # state directly: there is no provider to validate.
        self.config = _offline_agent_config()
        self.policy = policy
        self.policies = dict(policies or {})
        self.record: List[Dict[str, Any]] = []
        self.generators: List[ScriptedChatGenerator] = []

    def create_generator(
        self,
        agent_name: str,
        response_schema: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ScriptedChatGenerator:
        """Mirror the production factory's signature; return a scripted generator."""
        policy = self.policies.get(agent_name, self.policy)
        if policy is None:
            raise AssertionError(
                f"no scripted policy for agent {agent_name!r}. Add one to "
                f"`policies` — a silent default would let a test pass while "
                f"exercising nothing."
            )
        generator = ScriptedChatGenerator(
            policy=policy,
            response_schema=response_schema,
            agent_name=agent_name,
            record=self.record,
        )
        self.generators.append(generator)
        logger.debug("🧪 scripted generator for %s", agent_name)
        return generator

    # -- assertion helpers used by the suites -----------------------------------

    def calls_for(self, agent_name: str) -> List[Dict[str, Any]]:
        return [c for c in self.record if c["agent"] == agent_name]

    def tool_calls_made(self) -> List[str]:
        """Every tool name the scripted "model" asked for, in order."""
        return [name for call in self.record for name in call["tool_calls"]]


class scripted_llm:
    """Context manager installing a `ScriptedConfigManager` globally, then restoring.

    Restoration matters under xdist: a leaked fake manager would make a later test
    in the same worker silently offline (or a real-LLM test silently fake).

        with scripted_llm(policy=AlwaysAttackPolicy()) as manager:
            game.play_turn("attack the nearest enemy")
            assert "roll_skill_check" in manager.tool_calls_made()
    """

    def __init__(self, policy: Any = None, policies: Optional[Dict[str, Any]] = None):
        self.manager = ScriptedConfigManager(policy=policy, policies=policies)
        self._previous: Optional[LLMConfigManager] = None

    def __enter__(self) -> ScriptedConfigManager:
        try:
            self._previous = get_global_config_manager()
        except Exception:            # no manager yet, or no provider installed
            self._previous = None
        set_global_config_manager(self.manager)
        return self.manager

    def __exit__(self, *exc_info) -> None:
        set_global_config_manager(self._previous)
        return None
