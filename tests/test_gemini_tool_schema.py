"""
Gemini tool-schema and JSON-mode compatibility — found by scripts/playtest.py.

The live playtest passed its mechanism checks while EVERY scenario turn silently
fell back to a canned scene. Two Gemini API constraints were being violated, and
neither was reachable by a unit test that stopped short of a real call:

  1. tools + response_mime_type='application/json' -> 400 INVALID_ARGUMENT
     "Function calling with a response mime type: 'application/json' is
     unsupported". The scenario agent had both.

  2. Dict[str, Any] / Optional[...] tool params emit `additionalProperties` and
     `anyOf`, which Gemini's function-calling dialect rejects with
     "Unknown name ...: Cannot find field". The old cleaner stripped only
     top-level `default`, so these survived.

These tests assert on the converted payload, so they fail without needing the
network.
"""

import json

import pytest

from config.llm_utils import _sanitize_schema_for_gemini


pytestmark = pytest.mark.unit

FORBIDDEN = ("additionalProperties", "anyOf", "oneOf", "default", "title", "$schema")


def _forbidden_keys(payload) -> list:
    blob = json.dumps(payload)
    return [k for k in FORBIDDEN if k in blob]


class TestSanitizeSchema:
    """Bug 2: the schema dialect Gemini actually accepts."""

    def test_strips_additional_properties_from_dict_param(self):
        # Exactly what Dict[str, Any] produces.
        cleaned = _sanitize_schema_for_gemini(
            {"additionalProperties": True, "type": "object"})
        assert _forbidden_keys(cleaned) == []
        assert cleaned["type"] == "object"

    def test_collapses_optional_any_of_to_non_null_branch(self):
        # Exactly what Optional[Dict[str, Any]] produces.
        cleaned = _sanitize_schema_for_gemini({
            "anyOf": [{"additionalProperties": True, "type": "object"},
                      {"type": "null"}],
            "default": None,
        })
        assert _forbidden_keys(cleaned) == []
        assert cleaned["type"] == "object"

    def test_strips_nested_keys_not_just_top_level(self):
        """The old cleaner was shallow; this is the case it missed."""
        cleaned = _sanitize_schema_for_gemini({
            "type": "object",
            "properties": {
                "outer": {
                    "type": "object",
                    "properties": {
                        "inner": {"additionalProperties": True,
                                  "type": "object", "default": None},
                    },
                },
                "listy": {"type": "array",
                          "items": {"additionalProperties": True,
                                    "type": "object"}},
            },
        })
        assert _forbidden_keys(cleaned) == []

    def test_object_without_properties_gets_a_placeholder(self):
        """Gemini also rejects an object with no properties."""
        cleaned = _sanitize_schema_for_gemini(
            {"additionalProperties": True, "type": "object"})
        assert cleaned["properties"], "empty object schema is rejected by Gemini"

    def test_preserves_ordinary_fields(self):
        cleaned = _sanitize_schema_for_gemini(
            {"type": "string", "description": "a skill name"})
        assert cleaned == {"type": "string", "description": "a skill name"}

    def test_real_npc_tools_convert_cleanly(self):
        """The four tools whose declarations produced the live 400."""
        from agents.npc_controller_agent import (
            generate_npc_response, update_npc_memory,
            assess_attitude_change, determine_npc_action,
        )
        for tool in (generate_npc_response, update_npc_memory,
                     assess_attitude_change, determine_npc_action):
            converted = {name: _sanitize_schema_for_gemini(schema)
                         for name, schema in tool.parameters["properties"].items()}
            assert _forbidden_keys(converted) == [], f"{tool.name} still unsupported"

    def test_real_dm_tools_convert_cleanly(self):
        from agents.dm_tools import DM_TOOLS
        assert len(DM_TOOLS) == 13
        for tool in DM_TOOLS:
            converted = {name: _sanitize_schema_for_gemini(schema)
                         for name, schema in
                         (tool.parameters.get("properties") or {}).items()}
            assert _forbidden_keys(converted) == [], f"{tool.name} still unsupported"


class TestToolsDisableJsonMode:
    """Bug 1: tools and JSON mode are mutually exclusive on Gemini."""

    def _generator(self, response_schema=None):
        from config.llm_utils import GeminiChatGenerator
        return GeminiChatGenerator(
            model_name="gemini-2.5-flash",
            generation_config={"temperature": 0.7},
            response_schema=response_schema,
        )

    @staticmethod
    def _capturing_client(captured):
        """
        A client that records the config and returns a minimal VALID response.

        It must not raise to stop early: errors now propagate as GeminiAPIError
        (and an empty reply raises too), so a "stop here" exception would mask
        the assertion under test.
        """
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

        return _FakeClient()

    def test_schema_sets_json_mode_when_no_tools(self):
        generator = self._generator({"type": "object"})
        assert generator.generation_config["response_mime_type"] == "application/json"

    def test_json_mode_dropped_when_tools_present(self, monkeypatch):
        """
        The scenario agent passes BOTH. Sending them together is the 400 that
        made every scenario turn fall back to a canned scene.
        """
        from haystack.dataclasses import ChatMessage
        from agents.dm_tools import DM_TOOLS

        generator = self._generator({"type": "object"})
        captured = {}
        monkeypatch.setattr(generator, "client", self._capturing_client(captured))

        generator.run(messages=[ChatMessage.from_user("hi")], tools=DM_TOOLS)

        config = captured["config"]
        assert getattr(config, "tools", None), "tools should be sent"
        assert getattr(config, "response_mime_type", None) is None, \
            "JSON mode must be dropped when tools are present (Gemini 400s otherwise)"
        assert getattr(config, "response_schema", None) is None

    def test_json_mode_survives_across_calls(self, monkeypatch):
        """
        Dropping JSON mode must not mutate the generator's own config.

        The keys are removed from a per-call copy; if they were popped from
        self.generation_config, one tool call would permanently disable
        structured output for every later tool-less call on the same instance.
        """
        from haystack.dataclasses import ChatMessage
        from agents.dm_tools import DM_TOOLS

        generator = self._generator({"type": "object"})
        captured = {}
        monkeypatch.setattr(generator, "client", self._capturing_client(captured))

        generator.run(messages=[ChatMessage.from_user("hi")], tools=DM_TOOLS)
        generator.run(messages=[ChatMessage.from_user("hi")], tools=None)

        assert getattr(captured["config"], "response_mime_type", None) == \
            "application/json", "JSON mode was permanently lost after a tool call"

    def test_json_mode_kept_when_no_tools_passed(self, monkeypatch):
        """Structured output still works for the tool-less agents."""
        from haystack.dataclasses import ChatMessage

        generator = self._generator({"type": "object"})
        captured = {}
        monkeypatch.setattr(generator, "client", self._capturing_client(captured))

        generator.run(messages=[ChatMessage.from_user("hi")], tools=None)

        assert getattr(captured["config"], "response_mime_type", None) == \
            "application/json"


class TestErrorsRaiseInsteadOfBecomingReplies:
    """
    API faults must raise, not masquerade as the assistant's reply.

    Returning "Gemini API error: 403 Forbidden" AS THE REPLY meant a network
    fault reached the intent parser, which rejected it and logged "Failed to
    parse intent data ... No JSON object found in response" against
    pipeline_integration.py — blaming the wrong component for a network problem.
    """

    def _generator_raising(self, monkeypatch, exc):
        from config.llm_utils import GeminiChatGenerator

        generator = GeminiChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})

        class _FakeModels:
            def generate_content(self, model, contents, config):
                raise exc

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())
        return generator

    def test_api_error_raises(self, monkeypatch):
        from config.llm_utils import GeminiAPIError
        from haystack.dataclasses import ChatMessage

        generator = self._generator_raising(
            monkeypatch, RuntimeError("403 Forbidden"))

        with pytest.raises(GeminiAPIError):
            generator.run(messages=[ChatMessage.from_user("hi")])

    def test_error_text_is_never_returned_as_a_reply(self, monkeypatch):
        """The specific regression: the fault used to arrive as valid content."""
        from config.llm_utils import GeminiAPIError
        from haystack.dataclasses import ChatMessage

        generator = self._generator_raising(
            monkeypatch, RuntimeError("403 Forbidden"))
        try:
            result = generator.run(messages=[ChatMessage.from_user("hi")])
        except GeminiAPIError:
            return  # correct behaviour
        pytest.fail(f"error was returned as a reply instead of raised: {result}")

    def test_status_code_is_parsed(self, monkeypatch):
        from config.llm_utils import GeminiAPIError
        from haystack.dataclasses import ChatMessage

        for message, expected in (("403 Forbidden", 403),
                                  ("429 Too Many Requests", 429),
                                  ("503 Service Unavailable", 503)):
            generator = self._generator_raising(monkeypatch, RuntimeError(message))
            with pytest.raises(GeminiAPIError) as caught:
                generator.run(messages=[ChatMessage.from_user("hi")])
            assert caught.value.status_code == expected

    def test_retryable_classification(self):
        from config.llm_utils import GeminiAPIError

        assert GeminiAPIError("rate", status_code=429).retryable
        assert GeminiAPIError("boom", status_code=503).retryable
        assert not GeminiAPIError("bad key", status_code=403).retryable
        assert not GeminiAPIError("bad request", status_code=400).retryable

    def test_empty_response_raises_with_finish_reason(self, monkeypatch):
        """An empty reply means blocked or truncated, not 'nothing to say'."""
        from config.llm_utils import GeminiChatGenerator, GeminiAPIError
        from haystack.dataclasses import ChatMessage

        class _Candidate:
            finish_reason = type("R", (), {"name": "MAX_TOKENS"})()
            content = None

        class _Response:
            candidates = [_Candidate()]
            prompt_feedback = None
            text = ""

        generator = GeminiChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})

        class _FakeModels:
            def generate_content(self, model, contents, config):
                return _Response()

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())

        with pytest.raises(GeminiAPIError, match="MAX_TOKENS"):
            generator.run(messages=[ChatMessage.from_user("hi")])


class TestRetryStopsOnPermanentErrors:
    """generate_with_retry should not burn 3 attempts on a 403."""

    def test_permanent_error_is_not_retried(self):
        from components.retry_with_reasoning import generate_with_retry
        from config.llm_utils import GeminiAPIError

        attempts = {"n": 0}

        class _Generator:
            def run(self, messages):
                attempts["n"] += 1
                raise GeminiAPIError("403 Forbidden", status_code=403)

        result, info = generate_with_retry(
            _Generator(), [], validate=lambda t: t,
            fallback=lambda: "fell back", label="test")

        assert attempts["n"] == 1, f"retried a permanent error {attempts['n']}x"
        assert info["used_fallback"] is True

    def test_retryable_error_is_retried(self):
        from components.retry_with_reasoning import generate_with_retry
        from config.llm_utils import GeminiAPIError

        attempts = {"n": 0}

        class _Generator:
            def run(self, messages):
                attempts["n"] += 1
                raise GeminiAPIError("429 Too Many Requests", status_code=429)

        generate_with_retry(_Generator(), [], validate=lambda t: t,
                            max_attempts=3, fallback=lambda: "fell back",
                            label="test")

        assert attempts["n"] == 3, "a rate limit should be retried"
