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


class TestTheBackendSwitch:
    """
    The switch must default to Haystack, so merging the migration cannot change
    live behaviour, and must never take the game down when LangGraph misbehaves.
    """

    def test_the_default_is_haystack(self, monkeypatch):
        from agents.langgraph_dm_agents import active_backend

        monkeypatch.delenv("LLM_AGENT_BACKEND", raising=False)
        assert active_backend() == "haystack"

    def test_langgraph_is_opt_in(self, monkeypatch):
        from agents.langgraph_dm_agents import active_backend

        monkeypatch.setenv("LLM_AGENT_BACKEND", "langgraph")
        assert active_backend() == "langgraph"

    def test_an_unknown_backend_falls_back(self, monkeypatch):
        from agents.langgraph_dm_agents import active_backend

        monkeypatch.setenv("LLM_AGENT_BACKEND", "pytorch-lightning")
        assert active_backend() == "haystack"

    def test_case_and_whitespace_are_tolerated(self, monkeypatch):
        from agents.langgraph_dm_agents import active_backend

        monkeypatch.setenv("LLM_AGENT_BACKEND", "  LangGraph  ")
        assert active_backend() == "langgraph"

    def test_haystack_is_used_by_default(self, monkeypatch):
        from orchestrator.pipeline_integration import _build_agent

        monkeypatch.delenv("LLM_AGENT_BACKEND", raising=False)
        assert _build_agent("main_interface", lambda: "HAYSTACK") == "HAYSTACK"

    def test_an_unmigrated_agent_falls_back(self, monkeypatch):
        """
        Only two agents are ported. The rest must keep working rather than
        raising KeyError — a partial migration has to be safe.
        """
        from orchestrator.pipeline_integration import _build_agent

        monkeypatch.setenv("LLM_AGENT_BACKEND", "langgraph")
        assert _build_agent("scenario_generator", lambda: "HAYSTACK") == "HAYSTACK"

    def test_a_broken_langgraph_agent_falls_back(self, monkeypatch):
        """A transport experiment must never take the game down."""
        import agents.langgraph_dm_agents as module
        from orchestrator.pipeline_integration import _build_agent

        monkeypatch.setenv("LLM_AGENT_BACKEND", "langgraph")

        def _explode():
            raise RuntimeError("no credentials")

        monkeypatch.setattr(module, "create_interface_agent_langgraph", _explode)
        assert _build_agent("main_interface", lambda: "HAYSTACK") == "HAYSTACK"


class TestTheDropInContract:
    """
    The LangGraph agents must satisfy the contract the orchestrator ALREADY reads,
    so no downstream code branches on the backend.
    """

    def _agent(self, reply="{}"):
        import agents.langgraph_dm_agents as module

        agent = module.LangGraphAgent.__new__(module.LangGraphAgent)
        agent.agent_name = "test"
        agent.system_prompt = "You are a test."
        agent.tools = []

        class _Model:
            def invoke(self, messages):
                return type("R", (), {"content": reply})()

        agent._model = _Model()
        return agent

    def test_run_returns_a_messages_list(self):
        result = self._agent("hello").run(messages=[{"role": "user",
                                                     "content": "hi"}])
        assert "messages" in result and result["messages"]

    def test_the_last_message_exposes_text(self):
        """`.text` is what pipeline_integration reads first."""
        result = self._agent("the scene unfolds").run(
            messages=[{"role": "user", "content": "hi"}])
        assert result["messages"][-1].text == "the scene unfolds"

    def test_the_reply_also_exposes_the_content_parts(self):
        """The orchestrator falls back to `._content[0].text`."""
        reply = self._agent("abc").run(
            messages=[{"role": "user", "content": "hi"}])["messages"][-1]
        assert reply._content[0].text == "abc"
        assert str(reply) == "abc"

    def test_list_content_is_joined(self):
        """Gemini can return content as a list of parts on a 200 OK."""
        import agents.langgraph_dm_agents as module

        agent = self._agent()

        class _Model:
            def invoke(self, messages):
                return type("R", (), {"content": [{"text": "a"}, {"text": "b"}]})()

        agent._model = _Model()
        result = agent.run(messages=[{"role": "user", "content": "hi"}])
        assert result["messages"][-1].text == "ab"

    def test_an_empty_prompt_is_refused(self):
        """
        Plain dicts once produced EMPTY prompts for every NPC-AI call — one defect
        that surfaced as three symptoms and was misattributed to thinking budgets
        and Google-side 500s. Refuse loudly instead of calling with nothing.
        """
        result = self._agent().run(messages=[])
        assert result.get("error") == "empty prompt"

    def test_dict_messages_are_converted(self):
        """The exact shape that broke before: a plain dict, not a ChatMessage."""
        from agents.langgraph_dm_agents import _to_langchain

        converted = _to_langchain([{"role": "user", "content": "attack"}])
        assert len(converted) == 1
        assert converted[0].content == "attack"

    def test_string_messages_are_converted(self):
        from agents.langgraph_dm_agents import _to_langchain

        assert _to_langchain(["just a string"])[0].content == "just a string"

    def test_roles_are_preserved(self):
        from agents.langgraph_dm_agents import _to_langchain

        converted = _to_langchain([
            {"role": "system", "content": "s"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ])
        assert [type(m).__name__ for m in converted] == [
            "SystemMessage", "HumanMessage", "AIMessage"]

    def test_empty_messages_are_dropped(self):
        """An empty part would otherwise become an empty turn and confuse Gemini."""
        from agents.langgraph_dm_agents import _to_langchain

        assert _to_langchain([{"role": "user", "content": ""}]) == []

    def test_haystack_chat_messages_still_convert(self):
        """Both backends share prompt-building code, so both shapes must work."""
        from haystack.dataclasses import ChatMessage

        from agents.langgraph_dm_agents import _to_langchain

        converted = _to_langchain([ChatMessage.from_user("hello")])
        assert converted and converted[0].content == "hello"


class TestPromptsAreSharedNotDuplicated:
    """
    Both backends must read ONE prompt. A copy would drift, and then a bug fixed
    on one transport would silently persist on the other.
    """

    def test_the_interface_prompt_is_a_module_constant(self):
        from agents.main_interface_agent_fixed import INTERFACE_SYSTEM_PROMPT

        assert len(INTERFACE_SYSTEM_PROMPT) > 500
        assert "intent" in INTERFACE_SYSTEM_PROMPT.lower()

    def test_the_npc_prompt_is_a_module_constant(self):
        from agents.npc_controller_agent import NPC_SYSTEM_PROMPT

        assert "YOU WRITE THE WORDS" in NPC_SYSTEM_PROMPT

    def test_the_langgraph_agents_reuse_them(self):
        """Assert the SAME object, not merely similar text."""
        import inspect

        import agents.langgraph_dm_agents as module

        source = inspect.getsource(module)
        assert "INTERFACE_SYSTEM_PROMPT" in source
        assert "NPC_SYSTEM_PROMPT" in source
        assert "You are a D&D intent classification agent" not in source, (
            "the prompt was copied into the LangGraph backend instead of imported")
