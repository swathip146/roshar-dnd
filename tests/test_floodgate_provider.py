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


@pytest.fixture
def no_appleconnect(monkeypatch):
    """
    Disable the appleconnect source.

    It genuinely works on this machine, so without this the later fallbacks are
    unreachable and any test of them would be vacuous.
    """
    import config.floodgate as floodgate

    monkeypatch.setattr(floodgate, "APPLECONNECT_BIN", "/nonexistent/appleconnect")
    monkeypatch.setattr(floodgate, "_token_cache",
                        {"value": "", "obtained_at": 0.0})
    return floodgate


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

    def test_token_file_is_the_last_resort(self, monkeypatch, tmp_path, no_appleconnect):
        import config.floodgate as floodgate

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        token_file = tmp_path / ".hwtgenie"
        token_file.write_text("tok-from-file\n")
        monkeypatch.setattr(floodgate, "TOKEN_FILE", token_file)
        assert floodgate.get_floodgate_token() == "tok-from-file"

    def test_missing_credential_raises_an_actionable_error(self, monkeypatch, tmp_path, no_appleconnect):
        import config.floodgate as floodgate

        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        monkeypatch.setattr(floodgate, "TOKEN_FILE", tmp_path / "absent")
        with pytest.raises(floodgate.FloodgateUnavailable, match="hwtgenie login"):
            floodgate.get_floodgate_token()

    def test_optional_lookup_returns_none(self, monkeypatch, tmp_path, no_appleconnect):
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

    def test_missing_token_with_explicit_choice_also_logs(self, monkeypatch, tmp_path, caplog, no_appleconnect):
        import logging
        import config.floodgate as floodgate

        monkeypatch.setenv("LLM_PROVIDER", "floodgate")
        monkeypatch.delenv("FLOODGATE_TOKEN", raising=False)
        monkeypatch.delenv("HWTGENIE_API_KEY", raising=False)
        monkeypatch.setattr(floodgate, "TOKEN_FILE", tmp_path / "absent")
        with caplog.at_level(logging.ERROR):
            floodgate.resolve_provider()
        assert "no token was found" in caplog.text


class TestAppleconnectIsThePrimarySource:
    """
    `hwtgenie` is not installed on this machine and ~/.hwtgenie held a token that
    expired 187 days earlier, which is why a live LLM_PROVIDER=floodgate run
    failed on every turn. The credential path that actually works is
    `appleconnect getToken` — taken from pkg-wiki-cli's src/pkgwiki/core/auth.py,
    which reaches the same gateway.

    Two details matter and are easy to get wrong:
      - Floodgate authenticates with the ID token, NOT the access token.
      - appleconnect must run non-interactively, or it can block a turn on a UI.
    """

    def test_requests_the_id_token_not_the_access_token(self):
        import inspect
        import config.floodgate as floodgate

        source = inspect.getsource(floodgate._appleconnect_token)
        assert "oauth-id-token" in source
        assert "oauth-access-token" not in source

    def test_runs_non_interactively(self):
        """A UI prompt mid-turn would hang an unattended run."""
        import inspect
        import config.floodgate as floodgate

        source = inspect.getsource(floodgate._appleconnect_token)
        assert "--interactivity-type" in source
        assert '"none"' in source

    def test_uses_the_pkce_grant(self):
        import inspect
        import config.floodgate as floodgate

        assert '"pkce"' in inspect.getsource(floodgate._appleconnect_token)

    def test_tried_before_the_possibly_stale_file(self):
        """appleconnect mints fresh; the file may be months old."""
        import inspect
        import config.floodgate as floodgate

        source = inspect.getsource(floodgate.get_floodgate_token)
        assert source.index("_appleconnect_token") < source.index("TOKEN_FILE")

    def test_a_missing_binary_does_not_raise(self, monkeypatch):
        import config.floodgate as floodgate

        monkeypatch.setattr(floodgate, "APPLECONNECT_BIN", "/nonexistent/binary")
        floodgate._token_cache.update({"value": "", "obtained_at": 0.0})
        assert floodgate._appleconnect_token() is None

    def test_a_nonzero_exit_does_not_raise(self, monkeypatch):
        import subprocess
        import config.floodgate as floodgate

        class _Result:
            returncode = 1
            stdout = ""
            stderr = "not logged in"

        monkeypatch.setattr(floodgate, "APPLECONNECT_BIN", __file__)  # exists
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())
        floodgate._token_cache.update({"value": "", "obtained_at": 0.0})
        assert floodgate._appleconnect_token() is None

    def test_token_is_parsed_from_keyed_output(self, monkeypatch):
        import subprocess
        import config.floodgate as floodgate

        class _Result:
            returncode = 0
            stdout = ("oauth-access-token  aaaaaaaaaaaaaaaaaaaaaaaa\n"
                      "oauth-id-token  bbbbbbbbbbbbbbbbbbbbbbbbbb\n")
            stderr = ""

        monkeypatch.setattr(floodgate, "APPLECONNECT_BIN", __file__)
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())
        floodgate._token_cache.update({"value": "", "obtained_at": 0.0})
        assert floodgate._appleconnect_token() == "bbbbbbbbbbbbbbbbbbbbbbbbbb"

    def test_the_token_is_cached(self, monkeypatch):
        """A six-turn playtest must not shell out on every LLM call."""
        import subprocess
        import config.floodgate as floodgate

        calls = {"n": 0}

        class _Result:
            returncode = 0
            stdout = "oauth-id-token  " + "c" * 40
            stderr = ""

        def _run(*args, **kwargs):
            calls["n"] += 1
            return _Result()

        monkeypatch.setattr(floodgate, "APPLECONNECT_BIN", __file__)
        monkeypatch.setattr(subprocess, "run", _run)
        floodgate._token_cache.update({"value": "", "obtained_at": 0.0})

        first = floodgate._appleconnect_token()
        second = floodgate._appleconnect_token()
        assert first == second
        assert calls["n"] == 1, "appleconnect was invoked twice"

    def test_environment_still_overrides_appleconnect(self, monkeypatch):
        """An explicit token must win, for CI and for debugging."""
        from config.floodgate import get_floodgate_token

        monkeypatch.setenv("FLOODGATE_TOKEN", "explicit-token")
        assert get_floodgate_token() == "explicit-token"

class TestNativeGeminiTransport:
    """
    Floodgate speaks the NATIVE Gemini API, so the generator subclasses
    GeminiChatGenerator instead of reimplementing the request shape.

    An earlier version pointed at hwtgenie-dev.csg.apple.com through the OpenAI
    client and reimplemented tool conversion, schema handling and parsing. It
    also never connected: every call failed with "Connection error" even with a
    freshly minted token, because the HOST was wrong. pkg-wiki-cli reaches
    floodgate.g.apple.com successfully.
    """

    def test_uses_the_host_that_works(self):
        from config.floodgate import FLOODGATE_BASE_URL

        assert "floodgate.g.apple.com" in FLOODGATE_BASE_URL
        assert "hwtgenie" not in FLOODGATE_BASE_URL, (
            "that host refused every connection even with a valid token")

    def test_subclasses_the_gemini_generator(self):
        """Inheritance is what keeps tools, schemas and retries consistent."""
        from config.llm_utils import FloodgateChatGenerator, GeminiChatGenerator

        assert issubclass(FloodgateChatGenerator, GeminiChatGenerator)
        assert FloodgateChatGenerator.run is GeminiChatGenerator.run

    def test_model_name_is_not_prefixed_on_the_native_path(self):
        """"gcp:" belongs to the OpenAI gateway; here it would 404."""
        from config.floodgate import to_floodgate_model

        assert to_floodgate_model("gemini-2.5-flash") == "gemini-2.5-flash"
        assert to_floodgate_model("gcp:gemini-2.5-flash") == "gemini-2.5-flash"

    def test_client_carries_a_bearer_token(self):
        """The gateway authenticates from the header, not an API key."""
        from config.llm_utils import FloodgateChatGenerator

        generator = FloodgateChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})
        headers = generator.client._api_client._http_options.headers or {}
        assert headers.get("Authorization", "").startswith("Bearer ")

    def test_client_points_at_the_gateway(self):
        from config.llm_utils import FloodgateChatGenerator
        from config.floodgate import FLOODGATE_BASE_URL

        generator = FloodgateChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})
        assert str(generator.client._api_client._http_options.base_url).rstrip("/") \
            == FLOODGATE_BASE_URL.rstrip("/")

    def test_schema_enables_json_mode_like_the_parent(self):
        from config.llm_utils import FloodgateChatGenerator

        generator = FloodgateChatGenerator(
            model_name="gemini-2.5-flash", generation_config={},
            response_schema={"type": "object"})
        assert generator.generation_config["response_mime_type"] == "application/json"

    def test_project_token_header_is_sent_when_set(self, monkeypatch):
        from config.llm_utils import FloodgateChatGenerator

        monkeypatch.setenv("FLOODGATE_PROJECT_TOKEN", "proj-123")
        generator = FloodgateChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})
        headers = generator.client._api_client._http_options.headers or {}
        assert headers.get("X-Floodgate-Project-Token") == "proj-123"

    def test_inherits_the_transient_retry_policy(self):
        """The parent's 408/429/5xx backoff must apply here too."""
        from config.llm_utils import FloodgateChatGenerator

        assert FloodgateChatGenerator.MAX_TRANSIENT_RETRIES >= 1
        assert hasattr(FloodgateChatGenerator, "_generate_with_backoff")
