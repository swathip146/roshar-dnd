"""
Truncated intent JSON — found by scripts/playtest.py against the live API.

Two live turns logged "Failed to parse intent data from structured output: No
JSON object found in response" while the logged response text plainly BEGAN with
a JSON object. It was cut off mid-string:

    "rag_reasoning": "To generate an appropriate response ... ('Speak your First

Root cause: gemini-2.5-flash spends internal reasoning tokens against
max_output_tokens BEFORE emitting visible text. The log recorded
thoughts_token_count=802 and 956 against the interface agent's 1000-token cap,
so almost nothing was left for the payload.

Three separate defects, each fixed and covered here:
  1. thinking was enabled for a deterministic classification task
  2. the tuned per-agent caps were dead code — load_config_from_environment()
     (the path actually used) rebuilt every config from scratch as None
  3. a truncated reply was discarded wholesale, and misreported as absent
"""

import pytest


pytestmark = pytest.mark.unit


# Verbatim from the live log, turn 5.
LIVE_TRUNCATED = '''{
  "primary": "scenario_action",
  "action_verb": "call out",
  "arguments": "to see if anyone answers",
  "target": "anyone",
  "confidence": 0.9,
  "rationale": "Player is performing an action to elicit a response in the game world.",
  "rag_needed": true,
  "rag_query": "details about current location, potential NPCs, and quest-related entities",
  "rag_filters": "lore,npcs,campaigns",
  "rag_confidence": 0.9,
  "rag_category": "lore",
  "rag_reasoning": "To generate an appropriate response to the player's call, the system needs context on the current location, any present NPCs, and how the quest ('Speak your First'''

# Verbatim from the live log, turn 6 (truncated far earlier).
LIVE_TRUNCATED_SHORT = '{\n  "primary": "scenario_action",\n  "action_verb": "move",\n  "arguments": "on",'


class TestSalvageTruncatedJson:
    """Defect 3: recover the complete pairs instead of discarding everything."""

    def test_recovers_routing_fields_from_the_live_payload(self):
        from orchestrator.pipeline_integration import _salvage_truncated_json
        recovered = _salvage_truncated_json(LIVE_TRUNCATED)
        # `primary` is what actually decides the route.
        assert recovered["primary"] == "scenario_action"
        assert recovered["rag_needed"] is True
        assert recovered["confidence"] == 0.9

    def test_types_are_preserved(self):
        from orchestrator.pipeline_integration import _salvage_truncated_json
        recovered = _salvage_truncated_json(LIVE_TRUNCATED)
        assert isinstance(recovered["rag_needed"], bool)
        assert isinstance(recovered["confidence"], float)
        assert isinstance(recovered["primary"], str)

    def test_incomplete_trailing_string_is_dropped(self):
        """The half-written value must not be treated as complete."""
        from orchestrator.pipeline_integration import _salvage_truncated_json
        recovered = _salvage_truncated_json(LIVE_TRUNCATED)
        assert "rag_reasoning" not in recovered

    def test_recovers_from_a_very_early_truncation(self):
        from orchestrator.pipeline_integration import _salvage_truncated_json
        recovered = _salvage_truncated_json(LIVE_TRUNCATED_SHORT)
        assert recovered["primary"] == "scenario_action"
        assert recovered["action_verb"] == "move"

    def test_handles_escaped_quotes(self):
        from orchestrator.pipeline_integration import _salvage_truncated_json
        recovered = _salvage_truncated_json(
            '{"primary": "scenario_action", "rationale": "he said \\"go\\" loudly",')
        assert recovered["primary"] == "scenario_action"

    def test_empty_and_garbage_do_not_raise(self):
        from orchestrator.pipeline_integration import _salvage_truncated_json
        assert _salvage_truncated_json("") == {}
        assert _salvage_truncated_json("not json at all") == {}


class TestThinkingDisabledForClassification:
    """Defect 1: reasoning tokens starved the visible payload."""

    def test_interface_agent_disables_thinking(self):
        from config.llm_config import _tuned_agent_defaults
        assert _tuned_agent_defaults()["main_interface"].thinking_budget == 0

    def test_scenario_agent_keeps_thinking(self):
        """Narration benefits from reasoning; only extraction should disable it."""
        from config.llm_config import _tuned_agent_defaults
        assert _tuned_agent_defaults()["scenario_generator"].thinking_budget is None

    def test_thinking_budget_becomes_a_real_sdk_object(self, monkeypatch):
        """A plain dict would be rejected by the SDK."""
        from google.genai import types as genai_types
        from haystack.dataclasses import ChatMessage
        from config.llm_utils import GeminiChatGenerator

        generator = GeminiChatGenerator(
            model_name="gemini-2.5-flash",
            generation_config={"thinking_config": {"thinking_budget": 0}},
        )
        captured = {}

        class _Part:
            text = "ok"
            function_call = None

        class _Content:
            parts = [_Part()]

        class _Candidate:
            content = _Content()
            finish_reason = None

        class _Response:
            candidates = [_Candidate()]
            prompt_feedback = None
            text = "ok"

        class _FakeModels:
            def generate_content(self, model, contents, config):
                captured["config"] = config
                return _Response()

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())
        generator.run(messages=[ChatMessage.from_user("hi")])

        thinking = captured["config"].thinking_config
        assert isinstance(thinking, genai_types.ThinkingConfig)
        assert thinking.thinking_budget == 0


class TestTunedDefaultsActuallyApply:
    """
    Defect 2: the tuned values were dead code.

    get_global_config_manager() takes load_config_from_environment(), which built
    every LLMConfig from scratch. With the (normally unset) env vars absent,
    max_tokens and temperature came out None — so the scenario agent never got
    its 8000-token cap and the interface agent never got temperature=0.5.
    """

    def _fresh_manager(self):
        import config.llm_config as llm_config
        llm_config._global_config_manager = None
        return llm_config.get_global_config_manager()

    def test_interface_agent_has_a_real_token_cap(self):
        config = self._fresh_manager().config.main_interface
        assert config.max_tokens and config.max_tokens >= 2000, \
            "an unset cap is what let thinking truncate the payload"
        assert config.thinking_budget == 0

    def test_scenario_agent_gets_its_8000_token_cap(self):
        config = self._fresh_manager().config.scenario_generator
        assert config.max_tokens == 8000, \
            "the full scenario JSON does not fit in less"

    def test_temperatures_are_not_none(self):
        agents = self._fresh_manager().config
        assert agents.main_interface.temperature == 0.5
        assert agents.scenario_generator.temperature == 0.8

    def test_generation_config_reaches_the_generator(self):
        generator = self._fresh_manager().create_generator("main_interface")
        assert generator.generation_config["max_output_tokens"] >= 2000
        assert generator.generation_config["thinking_config"] == {"thinking_budget": 0}

    def test_environment_variables_still_override(self, monkeypatch):
        import config.llm_config as llm_config

        monkeypatch.setenv("MAIN_INTERFACE_MAX_TOKENS", "4321")
        monkeypatch.setenv("MAIN_INTERFACE_THINKING_BUDGET", "128")
        config = llm_config.load_config_from_environment().main_interface
        assert config.max_tokens == 4321
        assert config.thinking_budget == 128
