"""
Floodgate (hwtgenie) as an alternate route to Gemini, behind a provider switch.

WHY: the direct Gemini API returned HTTP 500 INTERNAL on EVERY npc_combat_ai call
in a live playtest, so every NPC degraded to "attack the nearest player" and the
tactical AI never ran. A second, independent transport means a Google-side outage
degrades the game rather than hollowing it out.

Floodgate is OpenAI-compatible and fronts the same Gemini models, so the switch
is a TRANSPORT choice: identical prompts, schemas and tools either way.

Credentials never enter the repo — env var, then hwtgenielib SSO, then
~/.hwtgenie (mode 600, outside the working tree).
"""

import json

import pytest
from haystack.dataclasses import ChatMessage


pytestmark = pytest.mark.unit


class TestProviderSwitch:

    def test_default_is_the_direct_api(self, monkeypatch):
        """Adding a provider must not silently reroute existing installs."""
        from config.floodgate import resolve_provider

        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert resolve_provider() == "gemini"

    def test_explicit_floodgate_is_honoured(self, monkeypatch):
        from config.floodgate import resolve_provider

        monkeypatch.setenv("LLM_PROVIDER", "floodgate")
        assert resolve_provider() == "floodgate"

    def test_auto_prefers_floodgate_when_a_token_exists(self, monkeypatch):
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "auto")
        monkeypatch.setattr(floodgate, "floodgate_available", lambda: True)
        assert floodgate.resolve_provider() == "floodgate"

    def test_auto_falls_back_when_no_token(self, monkeypatch):
        """A missing token must never be fatal."""
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "auto")
        monkeypatch.setattr(floodgate, "floodgate_available", lambda: False)
        assert floodgate.resolve_provider() == "gemini"

    def test_unknown_provider_falls_back(self, monkeypatch):
        from config.floodgate import resolve_provider

        monkeypatch.setenv("LLM_PROVIDER", "nonsense")
        assert resolve_provider() == "gemini"

    def test_argument_overrides_the_environment(self, monkeypatch):
        from config.floodgate import resolve_provider

        monkeypatch.setenv("LLM_PROVIDER", "floodgate")
        assert resolve_provider("gemini") == "gemini"


class TestTokenResolution:

    def test_environment_variables_win(self, monkeypatch):
        from config.floodgate import get_floodgate_token

        monkeypatch.setenv("FLOODGATE_TOKEN", "tok-from-env")
        assert get_floodgate_token() == "tok-from-env"

    def test_legacy_variable_is_accepted(self, monkeypatch):
        """knowledgebase uses HWTGENIE_API_KEY; stay compatible."""
        from config.floodgate import get_floodgate_token

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.setenv("HWTGENIE_API_KEY", "tok-legacy")
        assert get_floodgate_token() == "tok-legacy"

    def test_token_file_is_the_last_resort(self, monkeypatch, tmp_path):
        import config.floodgate as floodgate

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        token_file = tmp_path / ".hwtgenie"
        token_file.write_text("tok-from-file\n")
        monkeypatch.setattr(floodgate, "TOKEN_FILE", token_file)
        assert floodgate.get_floodgate_token() == "tok-from-file"

    def test_missing_credential_raises_an_actionable_error(self, monkeypatch, tmp_path):
        import config.floodgate as floodgate

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        monkeypatch.setattr(floodgate, "TOKEN_FILE", tmp_path / "absent")
        with pytest.raises(floodgate.FloodgateUnavailable, match="hwtgenie login"):
            floodgate.get_floodgate_token()

    def test_optional_lookup_returns_none(self, monkeypatch, tmp_path):
        import config.floodgate as floodgate

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        monkeypatch.setattr(floodgate, "TOKEN_FILE", tmp_path / "absent")
        assert floodgate.get_floodgate_token(required=False) is None

    def test_describe_never_leaks_the_token(self, monkeypatch):
        """describe() goes into startup logs, so it must be safe to print."""
        from config.floodgate import describe

        monkeypatch.setenv("FLOODGATE_TOKEN", "super-secret-value")
        assert "super-secret-value" not in json.dumps(describe())


class TestCredentialsAreGitIgnored:
    """The user asked for the same protection GEMINI_API_KEY has."""

    @pytest.mark.parametrize("path", [
        ".hwtgenie", ".hwtgenie.json", "floodgate_token.txt",
        "hwtgenie_token.txt", ".env", "secrets/token.txt",
    ])
    def test_credential_paths_are_ignored(self, path):
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(["git", "check-ignore", "-q", path],
                                cwd=root, capture_output=True)
        assert result.returncode == 0, f"{path} would be committable"


class TestModelNameTranslation:
    """Floodgate namespaces models by cloud; the direct API does not."""

    def test_gemini_gets_the_gcp_prefix(self):
        from config.floodgate import to_floodgate_model
        assert to_floodgate_model("gemini-2.5-flash") == "gcp:gemini-2.5-flash"

    def test_already_prefixed_names_pass_through(self):
        from config.floodgate import to_floodgate_model
        assert to_floodgate_model("gcp:gemini-2.5-pro") == "gcp:gemini-2.5-pro"
        assert to_floodgate_model("aws:anthropic.claude-opus-4-5-20251101-v1:0") \
            == "aws:anthropic.claude-opus-4-5-20251101-v1:0"

    def test_non_gemini_names_are_untouched(self):
        from config.floodgate import to_floodgate_model
        assert to_floodgate_model("gpt-4o-mini") == "gpt-4o-mini"


class TestFloodgatePayload:
    """The generator must speak OpenAI while behaving like the Gemini one."""

    def _generator(self, response_schema=None):
        from config.llm_utils import FloodgateChatGenerator

        generator = FloodgateChatGenerator.__new__(FloodgateChatGenerator)
        generator.model_name = "gcp:gemini-2.5-flash"
        generator.generation_config = {"temperature": 0.5,
                                       "max_output_tokens": 2000}
        generator.response_schema = response_schema
        return generator

    def test_token_cap_is_translated(self):
        """Gemini says max_output_tokens; OpenAI says max_tokens."""
        payload = self._generator()._build_payload(
            [ChatMessage.from_user("hi")], None)
        assert payload["max_tokens"] == 2000
        assert "max_output_tokens" not in payload

    def test_system_role_is_preserved(self):
        payload = self._generator()._build_payload(
            [ChatMessage.from_system("You are the DM."),
             ChatMessage.from_user("Look around.")], None)
        assert [m["role"] for m in payload["messages"]] == ["system", "user"]

    def test_schema_becomes_response_format_when_no_tools(self):
        payload = self._generator({"type": "object"})._build_payload(
            [ChatMessage.from_user("hi")], None)
        assert payload["response_format"]["type"] == "json_schema"

    def test_tools_suppress_the_schema(self):
        """Matches the direct route, where the two genuinely conflict."""
        from agents.dm_tools import DM_TOOLS

        payload = self._generator({"type": "object"})._build_payload(
            [ChatMessage.from_user("hi")], DM_TOOLS)
        assert len(payload["tools"]) == 13
        assert "response_format" not in payload

    def test_tool_schemas_are_sanitised(self):
        """Reuse the same cleaner; anyOf/additionalProperties break providers."""
        from agents.npc_controller_agent import generate_npc_response

        payload = self._generator()._build_payload(
            [ChatMessage.from_user("hi")], [generate_npc_response])
        blob = json.dumps(payload["tools"])
        assert "additionalProperties" not in blob
        assert "anyOf" not in blob

    def test_empty_message_list_still_produces_a_payload(self):
        payload = self._generator()._build_payload([], None)
        assert payload["messages"], "the API rejects an empty message list"


class TestFloodgateResponseParsing:

    def _parse(self, completion):
        from config.llm_utils import FloodgateChatGenerator
        return FloodgateChatGenerator._to_chat_message(completion)

    def test_text_response(self):
        class _Message:
            content = "The wind cuts across the ridge."
            tool_calls = None

        class _Choice:
            message = _Message()
            finish_reason = "stop"

        class _Completion:
            choices = [_Choice()]

        assert self._parse(_Completion()).text == "The wind cuts across the ridge."

    def test_tool_calls_become_haystack_toolcalls(self):
        class _Function:
            name = "roll_skill_check"
            arguments = '{"skill": "stealth", "dc": 13}'

        class _Call:
            id = "call_0"
            function = _Function()

        class _Message:
            content = None
            tool_calls = [_Call()]

        class _Choice:
            message = _Message()
            finish_reason = "tool_calls"

        class _Completion:
            choices = [_Choice()]

        calls = self._parse(_Completion()).tool_calls
        assert len(calls) == 1
        assert calls[0].tool_name == "roll_skill_check"
        assert calls[0].arguments == {"skill": "stealth", "dc": 13}

    def test_malformed_tool_arguments_do_not_raise(self):
        class _Function:
            name = "roll_dice"
            arguments = "{not json"

        class _Call:
            id = "c0"
            function = _Function()

        class _Message:
            content = None
            tool_calls = [_Call()]

        class _Choice:
            message = _Message()
            finish_reason = "tool_calls"

        class _Completion:
            choices = [_Choice()]

        assert self._parse(_Completion()).tool_calls[0].arguments == {}

    def test_empty_text_with_a_normal_stop_is_allowed(self):
        """Same rule as the direct route: STOP is success."""
        class _Message:
            content = ""
            tool_calls = None

        class _Choice:
            message = _Message()
            finish_reason = "stop"

        class _Completion:
            choices = [_Choice()]

        assert self._parse(_Completion()).text == ""

    def test_truncated_response_raises(self):
        from config.llm_utils import GeminiAPIError

        class _Message:
            content = ""
            tool_calls = None

        class _Choice:
            message = _Message()
            finish_reason = "length"

        class _Completion:
            choices = [_Choice()]

        with pytest.raises(GeminiAPIError, match="length"):
            self._parse(_Completion())


class TestSwitchIsWiredIntoTheConfigManager:

    def test_create_generator_consults_the_switch(self):
        import inspect
        from config import llm_config

        source = inspect.getsource(llm_config.LLMConfigManager._create_gemini_generator)
        assert "resolve_provider" in source
        assert "FloodgateChatGenerator" in source

    def test_floodgate_generator_shares_the_gemini_interface(self):
        """A transport swap must be invisible to every caller."""
        import inspect
        from config.llm_utils import FloodgateChatGenerator, GeminiChatGenerator

        for name in ("run", "__init__"):
            floodgate = set(inspect.signature(
                getattr(FloodgateChatGenerator, name)).parameters)
            gemini = set(inspect.signature(
                getattr(GeminiChatGenerator, name)).parameters)
            assert floodgate == gemini, f"{name} signatures diverge"

    def test_both_generators_raise_the_same_error_type(self):
        """Callers catch GeminiAPIError; Floodgate must not invent its own."""
        import inspect
        from config.llm_utils import FloodgateChatGenerator

        assert "GeminiAPIError" in inspect.getsource(FloodgateChatGenerator.run)


# The real token from a live run: issued 2026-03-06, expiry claim in the past.
# hwtgenie tokens carry x-oidc-id-exp, NOT a standard exp claim.
def _make_token(exp_epoch=None, claim="x-oidc-id-exp") -> str:
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    claims = {"x-oidc-email": "someone@example.com"}
    if exp_epoch is not None:
        claims[claim] = exp_epoch
    payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"


class TestExpiredTokensAreDetected:
    """
    A live run failed on EVERY turn with "Connection error" and quietly served
    canned scenes. The token was 187 days old and its x-oidc-id-exp claim had
    passed — but nothing checked, so the credential was never named as the cause.
    """

    def test_expired_token_is_reported(self):
        import time
        from config.floodgate import token_is_expired

        assert token_is_expired(_make_token(time.time() - 86400)) is True

    def test_valid_token_is_not_reported_as_expired(self):
        import time
        from config.floodgate import token_is_expired

        assert token_is_expired(_make_token(time.time() + 86400)) is False

    def test_standard_exp_claim_also_works(self):
        import time
        from config.floodgate import token_is_expired

        assert token_is_expired(_make_token(time.time() - 10, claim="exp")) is True

    def test_millisecond_expiry_is_handled(self):
        import time
        from config.floodgate import token_expiry

        expiry = token_expiry(_make_token(int((time.time() + 60) * 1000)))
        assert expiry is not None and abs(expiry - (time.time() + 60)) < 5

    def test_a_token_without_an_expiry_is_not_assumed_dead(self):
        """An unparseable expiry might still be a working token."""
        from config.floodgate import token_is_expired

        assert token_is_expired(_make_token(None)) is False

    def test_a_malformed_token_does_not_raise(self):
        from config.floodgate import token_expiry, token_is_expired

        assert token_expiry("not-a-jwt") is None
        assert token_is_expired("not-a-jwt") is False

    def test_expired_token_makes_floodgate_unavailable(self, monkeypatch):
        """Otherwise auto routes every call to a credential that cannot work."""
        import time
        import config.floodgate as floodgate

        monkeypatch.setenv("FLOODGATE_TOKEN", _make_token(time.time() - 86400))
        assert floodgate.floodgate_available() is False

    def test_auto_falls_back_when_the_token_is_expired(self, monkeypatch):
        import time
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "auto")
        monkeypatch.setenv("FLOODGATE_TOKEN", _make_token(time.time() - 86400))
        assert floodgate.resolve_provider() == "gemini"

    def test_explicit_floodgate_still_honoured_but_logs_why(self, monkeypatch, caplog):
        """
        The user asked for floodgate; do not silently override them — but the
        reason every call is about to fail must appear in the log.
        """
        import logging
        import time
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "floodgate")
        monkeypatch.setenv("FLOODGATE_TOKEN", _make_token(time.time() - 86400))
        with caplog.at_level(logging.ERROR):
            assert floodgate.resolve_provider() == "floodgate"
        assert "EXPIRED" in caplog.text
        assert "hwtgenie login" in caplog.text

    def test_missing_token_with_explicit_choice_also_logs(self, monkeypatch, tmp_path, caplog):
        import logging
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "floodgate")
        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        monkeypatch.setattr(floodgate, "TOKEN_FILE", tmp_path / "absent")
        with caplog.at_level(logging.ERROR):
            floodgate.resolve_provider()
        assert "no token was found" in caplog.text
