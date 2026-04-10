"""
Generate a new Gmail OAuth refresh token for local development.

Usage (PowerShell):
  cd backend
    .\\.venv\\Scripts\\python.exe scripts\\regenerate_gmail_refresh_token.py

Required env vars:
  GMAIL_CLIENT_ID
  GMAIL_CLIENT_SECRET

Flow:
  1) Script prints the consent URL.
  2) Open URL, grant consent, copy "code" from redirect URL.
  3) Paste code into the script.
  4) Script prints a new refresh token.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def _load_environment() -> None:
    # Ensure this script works when run directly from backend/ without importing settings.py.
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def build_consent_url(client_id: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(client_id: str, client_secret: str, code: str) -> dict:
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def main() -> None:
    _load_environment()

    client_id = _require_env("GMAIL_CLIENT_ID")
    client_secret = _require_env("GMAIL_CLIENT_SECRET")

    print("\nOpen this URL and complete consent:\n")
    print(build_consent_url(client_id))
    print("\nAfter consent, copy the authorization code and paste it below.\n")

    code = input("Authorization code: ").strip()
    if not code:
        raise RuntimeError("Authorization code is required")

    token_data = exchange_code_for_tokens(client_id, client_secret, code)
    refresh_token = token_data.get("refresh_token")

    if not refresh_token:
        raise RuntimeError(
            "No refresh_token returned. Ensure prompt=consent and access_type=offline, "
            "and use the same OAuth client configured in backend env."
        )

    print("\nNew GMAIL_REFRESH_TOKEN:\n")
    print(refresh_token)
    print("\nUpdate your backend .env and restart the API server.\n")


if __name__ == "__main__":
    main()
