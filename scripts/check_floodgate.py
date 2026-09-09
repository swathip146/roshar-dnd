#!/usr/bin/env python3
"""
Diagnose the Floodgate route in isolation — token, TLS, then one real call.

A full playtest takes minutes and buries the cause among game logs. This checks
the three things that can independently break, in order, and says which one did:

    1. credential   — can a token be minted, and is it fresh?
    2. TLS          — does the corporate root verify the gateway?
    3. round-trip   — does one real request return text?

    ./scripts/check_floodgate.py
"""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAIL = "❌"
OK = "✅"


def main() -> int:
    print("=" * 62)
    print("FLOODGATE CONNECTIVITY CHECK")
    print("=" * 62)

    from config.floodgate import (FLOODGATE_BASE_URL, ca_bundle, describe,
                                  get_floodgate_token, token_expiry,
                                  token_is_expired)

    info = describe()
    print(f"\ngateway: {FLOODGATE_BASE_URL}")
    print(f"provider currently selected: {info['provider']}")

    # 1 — credential
    print("\n1. Credential")
    try:
        token = get_floodgate_token()
    except Exception as e:
        print(f"   {FAIL} no token: {e}")
        return 1
    if token_is_expired(token):
        import datetime
        when = token_expiry(token)
        stamp = datetime.datetime.fromtimestamp(when) if when else "unknown"
        print(f"   {FAIL} token EXPIRED (expiry {stamp})")
        print("      appleconnect should mint a fresh one; check you are on the "
              "corporate network / VPN.")
        return 1
    print(f"   {OK} token resolved, {len(token)} chars, not expired")

    # 2 — TLS
    print("\n2. TLS trust")
    bundle = ca_bundle()
    if not bundle:
        print(f"   {FAIL} no CA bundle could be assembled")
        print("      Try: pip install --index-url https://pypi.apple.com/simple "
              "apple-certifi")
        return 1
    count = Path(bundle).read_text().count("BEGIN CERTIFICATE")
    print(f"   {OK} bundle: {bundle} ({count} certs)")

    host = FLOODGATE_BASE_URL.split("://", 1)[-1].split("/", 1)[0]
    try:
        import socket

        context = ssl.create_default_context(cafile=bundle)
        with socket.create_connection((host, 443), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                issuer = dict(x[0] for x in tls.getpeercert()["issuer"])
                print(f"   {OK} handshake verified (issuer: "
                      f"{issuer.get('organizationName', '?')})")
    except ssl.SSLCertVerificationError as e:
        print(f"   {FAIL} certificate NOT trusted: {e}")
        print("      The corporate root is missing from the bundle. Try: "
              "pip install --index-url https://pypi.apple.com/simple apple-certifi")
        return 1
    except PermissionError:
        print("   ⏭️  socket blocked by the sandbox — cannot verify from here")
    except Exception as e:
        print(f"   {FAIL} could not connect to {host}: {type(e).__name__}: {e}")
        print("      Check the corporate network / VPN.")
        return 1

    # 3 — one real request
    print("\n3. Round-trip")
    os.environ["LLM_PROVIDER"] = "floodgate"
    try:
        from haystack.dataclasses import ChatMessage

        from config.llm_utils import FloodgateChatGenerator

        generator = FloodgateChatGenerator(
            model_name="gemini-2.5-flash",
            generation_config={"temperature": 0.2, "max_output_tokens": 200},
        )
        reply = generator.run(messages=[
            ChatMessage.from_system("Answer in one short sentence."),
            ChatMessage.from_user("Name one hazard of a Rosharan highstorm."),
        ])
        text = reply["replies"][0].text
        print(f"   {OK} model replied: {text.strip()[:100]}")
    except Exception as e:
        print(f"   {FAIL} request failed: {type(e).__name__}: {str(e)[:220]}")
        return 1

    print("\n" + "=" * 62)
    print("Floodgate is working. Run the game with:")
    print("  LLM_PROVIDER=floodgate ./scripts/playtest.py --turns 6")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
