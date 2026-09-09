"""
Floodgate (hwtgenie) as an alternate route to Gemini — with a provider switch.

WHY: the direct Gemini API returned HTTP 500 INTERNAL on every npc_combat_ai
call during a live playtest, which silently reduced every NPC to "attack the
nearest player". A second, independent route to the same models means a
Google-side outage degrades the game instead of hollowing it out.

Floodgate is an OpenAI-COMPATIBLE proxy in front of both Anthropic and Google
models, so Gemini is reachable as "gcp:gemini-2.5-flash" through the OpenAI
client. That means the switch is a transport choice, not a model change: the same
prompts, schemas and tools work either way.

CREDENTIALS NEVER ENTER THE REPO. Resolution order, all outside the working tree:

    1. FLOODGATE_TOKEN / HWTGENIE_API_KEY   (environment)
    2. `appleconnect getToken` (PKCE, oauth-ID-token)  <- the one that works here
    3. hwtgenielib.perform_login()          (SSO, if installed)
    4. ~/.hwtgenie                          (file; may be stale)

The appleconnect path is taken from pkg-wiki-cli (src/pkgwiki/core/auth.py),
which reaches this gateway successfully; `hwtgenie` is not installed on this
machine and ~/.hwtgenie was 187 days stale. Floodgate needs the ID token, not the
access token. `.env` and `.hwtgenie*` are gitignored; the home-directory file is
mode 600 and outside the repo entirely.

Selecting the provider:

    LLM_PROVIDER=gemini      # default: direct Gemini API, needs GEMINI_API_KEY
    LLM_PROVIDER=floodgate   # via hwtgenie, needs a Floodgate token
    LLM_PROVIDER=auto        # Floodgate if a token is resolvable, else Gemini
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


FLOODGATE_BASE_URL = os.getenv(
    "FLOODGATE_BASE_URL",
    "https://hwtgenie-dev.csg.apple.com/api/floodgate/openai/v1",
)

# Floodgate namespaces its models by cloud. The direct API takes a bare name, so
# the same logical model has two spellings and the switch must translate.
_FLOODGATE_MODEL_PREFIX = "gcp:"

TOKEN_FILE = Path.home() / ".hwtgenie"


class FloodgateUnavailable(RuntimeError):
    """No Floodgate credential could be resolved."""


# appleconnect is the credential source that actually works on this machine.
# `hwtgenie` is not installed, and ~/.hwtgenie held a token that expired 187 days
# ago — which is why a live LLM_PROVIDER=floodgate run failed on every turn.
# These values, the PKCE grant and the ID-token (NOT access-token) requirement
# all come from pkg-wiki-cli's src/pkgwiki/core/auth.py, which reaches the same
# gateway successfully.
APPLECONNECT_BIN = os.getenv("APPLECONNECT_BIN", "/usr/local/bin/appleconnect")
FLOODGATE_CLIENT_ID = os.getenv(
    "FLOODGATE_CLIENT_ID", "hvys3fcwcteqrvw3qzkvtk86viuoqv")
FLOODGATE_SCOPES = os.getenv(
    "FLOODGATE_SCOPES", "openid,dsid,accountname,profile,groups")

# Floodgate ID tokens are short-lived. Cache for 25 minutes so a six-turn
# playtest does not shell out on every single LLM call.
_TOKEN_TTL_SECONDS = 25 * 60
_token_cache: dict = {"value": "", "obtained_at": 0.0}


def _appleconnect_token() -> Optional[str]:
    """
    Mint a fresh Floodgate ID token via `appleconnect getToken`.

    Floodgate authenticates with the ID token, not the access token — asking for
    the wrong one yields a token that is rejected. Returns None (never raises) so
    the caller can fall through to the other sources.
    """
    import subprocess
    import time

    cached = _token_cache
    if cached["value"] and (time.time() - cached["obtained_at"]) < _TOKEN_TTL_SECONDS:
        return cached["value"]

    if not Path(APPLECONNECT_BIN).exists():
        logger.debug(f"   appleconnect not found at {APPLECONNECT_BIN}")
        return None

    command = [
        APPLECONNECT_BIN, "getToken",
        "-t", "oauth",
        "-G", "pkce",
        "-C", FLOODGATE_CLIENT_ID,
        "-o", FLOODGATE_SCOPES,
        # Never pop a UI in the middle of a turn; fail and fall back instead.
        "--interactivity-type", "none",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=30)
    except Exception as e:
        logger.debug(f"   appleconnect failed to run: {e}")
        return None

    if result.returncode != 0:
        logger.debug(
            f"   appleconnect exit {result.returncode}: "
            f"{(result.stderr or '').strip()[:200]}")
        return None

    output = (result.stdout or "").strip()
    token = None
    for line in output.splitlines():
        if "oauth-id-token" in line:
            parts = line.split(None, 1)
            if len(parts) == 2:
                token = parts[1].strip()
                break
    if token is None and "\n" not in output and len(output) > 20:
        token = output

    if token:
        _token_cache.update({"value": token, "obtained_at": time.time()})
        logger.debug("🔐 Floodgate ID token minted via appleconnect")
        return token

    logger.debug("   could not extract oauth-id-token from appleconnect output")
    return None


def get_floodgate_token(required: bool = True) -> Optional[str]:
    """
    Resolve a Floodgate token WITHOUT reading anything from the repo.

    Args:
        required: raise FloodgateUnavailable if nothing is found; otherwise
            return None so callers can fall back to the direct API.
    """
    for variable in ("FLOODGATE_TOKEN", "HWTGENIE_API_KEY"):
        token = (os.getenv(variable) or "").strip()
        if token:
            logger.debug(f"🔐 Floodgate token from ${variable}")
            return token

    # appleconnect first: it mints a FRESH token, whereas ~/.hwtgenie may be
    # months out of date (it was, by 187 days, in a live run).
    token = _appleconnect_token()
    if token:
        return token

    # SSO login, when the library is installed. Optional by design: the file
    # fallback below covers machines without it.
    try:
        import hwtgenielib

        result = hwtgenielib.perform_login()
        if isinstance(result, str) and result.strip():
            logger.debug("🔐 Floodgate token from hwtgenielib.perform_login()")
            return result.strip()
        token = (getattr(result, "access_token", None)
                 or getattr(result, "token", None))
        if token:
            logger.debug("🔐 Floodgate token from hwtgenielib result object")
            return str(token).strip()
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"   hwtgenielib login unavailable: {e}")

    try:
        token = TOKEN_FILE.read_text().strip()
        if token:
            logger.debug(f"🔐 Floodgate token from {TOKEN_FILE}")
            return token
    except (FileNotFoundError, PermissionError):
        pass

    if required:
        raise FloodgateUnavailable(
            "No Floodgate credential found. Set FLOODGATE_TOKEN, or run "
            "'hwtgenie login' to write ~/.hwtgenie."
        )
    return None


def token_expiry(token: str) -> Optional[float]:
    """
    Read the expiry out of an hwtgenie JWT without verifying it.

    The token has no standard `exp`; it carries `x-oidc-id-exp` (epoch seconds).
    Returns None when it cannot be determined — never raises, since a token we
    cannot parse might still be perfectly valid.
    """
    import base64
    import json

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None

    for key in ("exp", "x-oidc-id-exp"):
        raw = claims.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        # Some claims are milliseconds.
        return value / 1000 if value > 1e11 else value
    return None


def token_is_expired(token: str) -> bool:
    """True only when the token's expiry is known AND in the past."""
    import time

    expiry = token_expiry(token)
    return expiry is not None and expiry < time.time()


def floodgate_available() -> bool:
    """
    Whether a USABLE Floodgate token can be resolved right now.

    An expired token counts as unavailable. Otherwise LLM_PROVIDER=auto would
    happily route every call to a credential that cannot work — which is what
    happened in a live run: a token 187 days stale produced a connection-level
    failure on every turn and the game fell back to canned scenes without ever
    saying the credential was the problem.
    """
    try:
        token = get_floodgate_token(required=False)
        if not token:
            return False
        if token_is_expired(token):
            logger.warning(
                "⚠️ The Floodgate token has EXPIRED "
                f"({TOKEN_FILE} was written "
                f"{_days_old(TOKEN_FILE)}). Run 'hwtgenie login' to refresh it."
            )
            return False
        return True
    except Exception:
        return False


def _days_old(path: Path) -> str:
    """Human-readable file age, for the expiry warning."""
    import time

    try:
        return f"{(time.time() - path.stat().st_mtime) / 86400:.0f} days ago"
    except Exception:
        return "at an unknown time"


def to_floodgate_model(model_name: str) -> str:
    """
    Translate a direct-API model name into its Floodgate spelling.

    "gemini-2.5-flash" -> "gcp:gemini-2.5-flash". Already-prefixed names and
    non-Gemini models (Anthropic via "aws:") pass through untouched.
    """
    if ":" in model_name:
        return model_name
    if model_name.startswith("gemini"):
        return f"{_FLOODGATE_MODEL_PREFIX}{model_name}"
    return model_name


def resolve_provider(requested: Optional[str] = None) -> str:
    """
    Decide which transport to use: "floodgate" or "gemini".

    "auto" prefers Floodgate when a token is resolvable, because it is the route
    that survives a Google-side outage; it falls back to the direct API rather
    than failing, so a missing token is never fatal.
    """
    choice = (requested or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()

    if choice == "floodgate":
        # Explicit choice: honour it, but say plainly if the credential is dead.
        # A live run with a 187-day-old token failed on every turn with
        # "Connection error" and the game quietly served canned scenes — the
        # credential was never named as the cause.
        token = get_floodgate_token(required=False)
        if not token:
            logger.error(
                "❌ LLM_PROVIDER=floodgate but no token was found. Run "
                "'hwtgenie login', or set LLM_PROVIDER=gemini.")
        elif token_is_expired(token):
            logger.error(
                "❌ LLM_PROVIDER=floodgate but the token is EXPIRED "
                f"({TOKEN_FILE}, {_days_old(TOKEN_FILE)}). Every call will "
                "fail. Run 'hwtgenie login' to refresh it.")
        return "floodgate"
    if choice == "auto":
        if floodgate_available():
            logger.info("🔀 LLM_PROVIDER=auto → floodgate (token found)")
            return "floodgate"
        logger.info("🔀 LLM_PROVIDER=auto → gemini (no Floodgate token)")
        return "gemini"
    if choice not in ("gemini", "google"):
        logger.warning(
            f"⚠️ Unknown LLM_PROVIDER={choice!r}; using the direct Gemini API")
    return "gemini"


def describe() -> dict:
    """Diagnostics for startup logs and the playtest — never includes the token."""
    return {
        "provider": resolve_provider(),
        "floodgate_available": floodgate_available(),
        "floodgate_base_url": FLOODGATE_BASE_URL,
        "gemini_key_present": bool(os.getenv("GEMINI_API_KEY")
                                   or os.getenv("GOOGLE_API_KEY")),
        "token_file_present": TOKEN_FILE.exists(),
    }
