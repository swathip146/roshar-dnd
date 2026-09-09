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

        class _FakeModels:
            def generate_content(self, model, contents, config):
                captured["config"] = config
                raise RuntimeError("stop here — only the config matters")

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())

        generator.run(messages=[ChatMessage.from_user("hi")], tools=DM_TOOLS)

        config = captured["config"]
        assert getattr(config, "tools", None), "tools should be sent"
        assert getattr(config, "response_mime_type", None) is None, \
            "JSON mode must be dropped when tools are present (Gemini 400s otherwise)"
        assert getattr(config, "response_schema", None) is None

    def test_json_mode_kept_when_no_tools_passed(self, monkeypatch):
        """Structured output still works for the tool-less agents."""
        from haystack.dataclasses import ChatMessage

        generator = self._generator({"type": "object"})
        captured = {}

        class _FakeModels:
            def generate_content(self, model, contents, config):
                captured["config"] = config
                raise RuntimeError("stop here")

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())
        generator.run(messages=[ChatMessage.from_user("hi")], tools=None)

        assert getattr(captured["config"], "response_mime_type", None) == \
            "application/json"
