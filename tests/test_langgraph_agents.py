"""
The LangGraph/LangChain agent-layer seam (plan §4, Phase 3.5).

Why the migration is a constraint rather than a preference: Haystack 2.21
(pinned) has `AgentBreakpoint`/`AgentSnapshot`; 3.0 REMOVED them, and current
Gemini integrations require >= 3.0. `requirements.txt` says `haystack-ai>=2.0.0`,
so a fresh install floats to 3.x and the agents break — the build is not
reproducible today.

These tests cover the seam WITHOUT calling the network. The live route is proven
separately (a real call through the-optional-gateway returned 200 OK for plain
text, structured output and tool calling); what matters here is that the
configuration handed to the model is correct, because that is where the
previously-dead tuned settings hid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]


class TestTheDependenciesArePresent:
    def test_langgraph_is_importable(self):
        from agents.langgraph_models import langgraph_available
        assert langgraph_available() is True, (
            "langgraph / langchain-google-genai are required for the agent layer")

    def test_langchain_uses_the_current_google_sdk(self):
        """
        Phase 4 ported off the deprecated `google.generativeai`. If LangChain
        pulled the old SDK back in, gateway's transport and CA bundle would not
        apply — so pin the expectation.
        """
        import inspect

        import langchain_google_genai.chat_models as chat_models

        source = inspect.getsource(chat_models)
        assert "from google import genai" in source, (
            "langchain-google-genai no longer uses the current google-genai SDK")

    def test_the_model_accepts_a_custom_base_url(self):
        """gateway is reachable only if base_url is supported."""
        import inspect

        from langchain_google_genai import ChatGoogleGenerativeAI

        parameters = inspect.signature(ChatGoogleGenerativeAI).parameters
        assert "base_url" in parameters or "client_options" in parameters
        assert "additional_headers" in parameters, (
            "no way to send the gateway bearer token")


class TestPerAgentSettingsAreApplied:
    """
    The tuned per-agent LLM settings were once DEAD CODE:
    `load_config_from_environment()` — the path actually taken — rebuilt every
    config from scratch, so with env vars unset `max_tokens` and `temperature`
    were `None` for every agent and the scenario agent never received its
    8000-token cap. This seam reads the same config, so it must not reintroduce
    that.
    """

    @pytest.mark.parametrize("agent_name", [
        "scenario_generator", "rag_retriever", "npc_controller",
        "main_interface", "npc_combat_ai", "combat_init", "combat_narrative",
    ])
    def test_every_agent_has_real_settings(self, agent_name):
        from agents.langgraph_models import _agent_settings

        settings = _agent_settings(agent_name)
        assert settings["temperature"] is not None, f"{agent_name}: null temperature"
        assert settings["max_tokens"] is not None, f"{agent_name}: null max_tokens"
        assert 0 <= settings["temperature"] <= 2, settings["temperature"]
        assert settings["max_tokens"] > 0

    def test_the_scenario_agent_gets_a_large_budget(self):
        """It writes prose and must not be truncated mid-scene."""
        from agents.langgraph_models import _agent_settings

        assert _agent_settings("scenario_generator")["max_tokens"] >= 4000

    def test_extraction_agents_are_deterministic(self):
        """
        Intent routing must be reproducible; a creative temperature here makes
        the same input route differently on different turns.
        """
        from agents.langgraph_models import _agent_settings

        assert _agent_settings("main_interface")["temperature"] <= 0.5

    def test_extraction_agents_disable_thinking(self):
        """
        Reasoning tokens count against max_output_tokens: budgets of 802 and 956
        against a 1000-token cap truncated the intent JSON mid-string. Structured
        extraction runs with thinking off.
        """
        from agents.langgraph_models import _agent_settings

        for agent_name in ("main_interface", "npc_combat_ai", "combat_init"):
            budget = _agent_settings(agent_name)["thinking_budget"]
            assert budget == 0, (
                f"{agent_name} has thinking_budget={budget}; reasoning tokens "
                f"will eat its output budget")

    def test_the_agent_list_matches_the_llm_config(self):
        """A name in one and not the other silently takes default_fallback —
        which is how the combat agents ended up with thinking enabled."""
        from agents.langgraph_models import AGENT_NAMES
        from config.llm_config import get_global_config_manager

        config = get_global_config_manager().config
        for name in AGENT_NAMES:
            assert getattr(config, name, None) is not None, (
                f"{name} is missing from AgentLLMConfig")


class TestSchemaAndToolsAreNotCombined:
    """
    Gemini returns HTTP 400 for a request carrying BOTH tools and
    `response_mime_type="application/json"`. The scenario agent had both, so
    EVERY scenario turn fell back to a canned scene. Tools must win.
    """

    def test_tools_win_and_the_schema_is_dropped(self, monkeypatch):
        captured = {}

        class _FakeModel:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def bind_tools(self, tools):
                captured["bound_tools"] = tools
                return self

        import agents.langgraph_models as module

        monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI",
                            _FakeModel)
        monkeypatch.setattr(module, "_gateway_kwargs", lambda: {"api_key": "x"})
        monkeypatch.setenv("LLM_PROVIDER", "gemini")

        module.create_chat_model(
            "scenario_generator",
            response_schema={"type": "object"},
            tools=[lambda: None])

        assert "response_schema" not in captured, (
            "tools + response_schema together return HTTP 400 from Gemini")
        assert "response_mime_type" not in captured
        assert captured.get("bound_tools"), "the tools were dropped instead"

    def test_a_schema_alone_is_applied(self, monkeypatch):
        captured = {}

        class _FakeModel:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import agents.langgraph_models as module

        monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI",
                            _FakeModel)
        monkeypatch.setenv("LLM_PROVIDER", "gemini")

        module.create_chat_model("main_interface",
                                 response_schema={"type": "object"})
        assert captured.get("response_mime_type") == "application/json"
        assert captured.get("response_schema") == {"type": "object"}


class TestTheTransportIsPreserved:
    def test_gateway_sends_a_bearer_token(self, monkeypatch):
        import agents.langgraph_models as module

        monkeypatch.setattr(module, "_model_name", lambda: "gemini-2.5-flash")
        monkeypatch.setattr("config.gateway.get_gateway_token",
                            lambda: "test-token")
        monkeypatch.setattr("config.gateway.ssl_context", lambda: None)

        kwargs = module._gateway_kwargs()
        assert kwargs["additional_headers"]["Authorization"] == "Bearer test-token"
        assert "gateway" in kwargs["base_url"]

    def test_a_missing_token_fails_loudly(self, monkeypatch):
        """Never silently fall back to the direct API — that hides an outage."""
        import agents.langgraph_models as module

        monkeypatch.setattr("config.gateway.get_gateway_token", lambda: "")
        with pytest.raises(RuntimeError, match="gateway"):
            module._gateway_kwargs()

    def test_tls_verification_is_never_disabled(self):
        """A hard rule: the corporate CA is assembled, never bypassed."""
        source = (PROJECT_ROOT / "agents" / "langgraph_models.py").read_text()
        assert "verify=False" not in source
        assert "verify\": False" not in source

    def test_the_provider_switch_is_respected(self, monkeypatch):
        captured = {}

        class _FakeModel:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import agents.langgraph_models as module

        monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI",
                            _FakeModel)
        monkeypatch.setattr(module, "_gateway_kwargs",
                            lambda: {"api_key": "unused", "base_url": "fg"})

        monkeypatch.setattr("config.gateway.resolve_provider",
                            lambda: "gateway")
        module.create_chat_model("main_interface")
        assert captured.get("base_url") == "fg"

        captured.clear()
        monkeypatch.setattr("config.gateway.resolve_provider",
                            lambda: "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "direct-key")
        module.create_chat_model("main_interface")
        assert captured.get("api_key") == "direct-key"
        assert "base_url" not in captured
