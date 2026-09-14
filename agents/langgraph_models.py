"""
LangGraph/LangChain chat models for the agent layer (plan §4, Phase 3.5).

Why this exists — the reason is a hard constraint, not a preference:

Haystack 2.21 (pinned) has `AgentBreakpoint`/`AgentSnapshot`; **3.0 removed
them**, with release notes stating that pausing and resuming execution inside an
Agent is no longer supported. Meanwhile current Gemini integrations
(`google-genai-haystack` >= 5.0) require Haystack >= 3.0. So the agent layer is
pinned between an unsupported branch and a breaking upgrade that costs the one
capability the game needs. `requirements.txt` also declares `haystack-ai>=2.0.0`,
so a fresh install floats to 3.x and the agents break.

This module is the seam. It produces `langchain_google_genai.ChatGoogleGenerativeAI`
instances configured exactly like `LLMConfigManager.create_generator()` — same
per-agent temperature, token cap and thinking budget — and, critically, **over
the same transport**, including an optional corporate gateway with its own CA bundle.

Verified against the live gateway: `langchain-google-genai` builds on
`from google import genai` (the same current SDK the project ported to in Phase 4)
and accepts `base_url`, so gateway works unchanged. A real call through
the gateway returned 200 OK.

Nothing here decides game rules. The LLM narrates; code adjudicates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


# Agent names shared with LLMConfigManager, so both transports read one config.
AGENT_NAMES = (
    "scenario_generator", "rag_retriever", "npc_controller", "main_interface",
    "npc_combat_ai", "combat_init", "combat_narrative",
)


def langgraph_available() -> bool:
    """True if the LangGraph/LangChain agent layer can be built."""
    try:
        import langgraph  # noqa: F401
        import langchain_google_genai  # noqa: F401
        return True
    except ImportError:
        return False


def _agent_settings(agent_name: str) -> Dict[str, Any]:
    """
    Read one agent's tuned settings from the existing LLM config.

    Deliberately reuses `LLMConfigManager` rather than re-deriving anything: the
    tuned per-agent values were once dead code (`load_config_from_environment()`
    rebuilt every config from scratch, so `max_tokens` and `temperature` were
    `None` for every agent and the scenario agent never got its 8000-token cap).
    One source of truth avoids a second copy of that bug.
    """
    settings = {"temperature": 0.7, "max_tokens": 2048, "thinking_budget": None}
    try:
        from config.llm_config import get_global_config_manager

        manager = get_global_config_manager()
        config = getattr(manager.config, agent_name, None)
        if config is not None:
            for key in ("temperature", "max_tokens", "thinking_budget"):
                value = getattr(config, key, None)
                if value is not None:
                    settings[key] = value
    except Exception as e:
        logger.debug(f"   Falling back to default LLM settings for "
                     f"{agent_name}: {e}")
    return settings


def create_chat_model(agent_name: str = "scenario_generator",
                      response_schema: Optional[Dict[str, Any]] = None,
                      tools: Optional[List[Any]] = None) -> Any:
    """
    Build a LangChain chat model for one agent, over the active transport.

    Mirrors `LLMConfigManager.create_generator()`:
      * per-agent temperature / max_tokens / thinking_budget
      * gateway or the direct Gemini API, per `LLM_PROVIDER`
      * structured output via `response_schema` when asked

    Args:
        agent_name: one of AGENT_NAMES.
        response_schema: JSON schema for structured output. Mutually exclusive
            with `tools` — Gemini returns HTTP 400 for a request carrying both,
            which silently reduced every scenario turn to a canned scene until it
            was found. Tools win; the schema is dropped with a warning.
        tools: LangChain tools to bind.

    Returns:
        A `ChatGoogleGenerativeAI`, with tools bound if supplied.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    # Optional machine-local gateway; absent, use the direct Gemini API.
    try:
        from config.gateway import resolve_provider
    except ImportError:
        resolve_provider = lambda: "gemini"

    settings = _agent_settings(agent_name)
    kwargs: Dict[str, Any] = {
        "model": _model_name(),
        "temperature": settings["temperature"],
        "max_output_tokens": settings["max_tokens"],
    }

    # Thinking tokens count against max_output_tokens. A budget of 802 and 956
    # against a 1000-token cap truncated the intent JSON mid-string, so
    # extraction agents run with thinking OFF.
    budget = settings.get("thinking_budget")
    if budget is not None:
        kwargs["thinking_budget"] = budget

    provider = resolve_provider()
    if provider == "gateway":
        kwargs.update(_gateway_kwargs())
    else:
        kwargs["api_key"] = _gemini_api_key()

    if tools and response_schema:
        logger.warning(
            "⚠️ tools + response_schema together return HTTP 400 from Gemini; "
            "keeping tools and dropping the schema for this call")
        response_schema = None

    if response_schema:
        kwargs["response_mime_type"] = "application/json"
        kwargs["response_schema"] = response_schema

    model = ChatGoogleGenerativeAI(**kwargs)
    logger.info(f"🧠 LangChain model for {agent_name} via {provider} "
                f"(temp={kwargs['temperature']}, "
                f"max_tokens={kwargs['max_output_tokens']}, "
                f"tools={len(tools) if tools else 0})")

    if tools:
        return model.bind_tools(tools)
    return model


def _model_name() -> str:
    import os
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _gemini_api_key() -> str:
    import os
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        logger.warning("⚠️ GEMINI_API_KEY is not set")
    return key


def _gateway_kwargs() -> Dict[str, Any]:
    """
    Point the model at gateway, with the corporate CA bundle.

    The network terminates TLS with an internal root that is in the macOS
    keychain but not in certifi's bundle, so a default client fails with
    CERTIFICATE_VERIFY_FAILED. `config.gateway.ssl_context()` assembles a bundle
    from the system keychains. Verification is NEVER disabled.

    `config/gateway.py` is machine-local and untracked, so this path only exists on
    a host that provides it.
    """
    from config.gateway import (GATEWAY_BASE_URL, get_gateway_token,
                                ssl_context)

    token = get_gateway_token()
    if not token:
        raise RuntimeError(
            "LLM_PROVIDER=gateway but no token could be resolved; "
            "see ./scripts/check_gateway.py")

    kwargs: Dict[str, Any] = {
        # api_key is required by the constructor but unused on this route: the
        # gateway authenticates from the Authorization header.
        "api_key": "unused-gateway-route",
        "base_url": GATEWAY_BASE_URL,
        "additional_headers": {"Authorization": f"Bearer {token}"},
    }
    try:
        context = ssl_context()
        if context is not None:
            kwargs["client_args"] = {"verify": context}
    except Exception as e:
        # Do not fall back to an unverified client — fail loudly instead.
        logger.warning(f"⚠️ Could not build the gateway CA bundle: {e}")
    return kwargs
