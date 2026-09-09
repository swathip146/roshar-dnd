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
    2. hwtgenielib.perform_login()          (SSO, if installed)
    3. ~/.hwtgenie                          (file written by `hwtgenie login`)

This mirrors how /Users/scj/Documents/Projects/AI/knowledgebase reaches the same
endpoint. `.env` and `.hwtgenie*` are gitignored; the home-directory file is
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


def floodgate_available() -> bool:
    """Whether a Floodgate token can be resolved right now."""
    try:
        return bool(get_floodgate_token(required=False))
    except Exception:
        return False


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
