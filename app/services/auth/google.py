"""Google OAuth 2.0 (Authorization Code) — server-side sign-in.

No client-side Google SDK: the browser is redirected to Google, Google redirects
back to our callback with a ``code``, and we exchange it server-side for the
user's verified identity (email, name, picture, hosted domain).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint
_SCOPE = "openid email profile"


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None
    hd: str | None  # hosted (Workspace) domain, if any


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _SCOPE,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str
) -> GoogleIdentity:
    """Exchange an auth code for tokens and return the verified identity.

    Raises ``ValueError`` on any failure (network, bad code, unverified email).
    """
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token as g_id_token

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                _TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:  # pragma: no cover - network
        raise ValueError(f"Token exchange failed: {exc}") from exc

    if resp.status_code != 200:
        raise ValueError(f"Token exchange rejected ({resp.status_code}): {resp.text[:200]}")

    tok = resp.json().get("id_token")
    if not tok:
        raise ValueError("No id_token in Google's response.")

    try:
        claims = g_id_token.verify_oauth2_token(tok, g_requests.Request(), client_id)
    except Exception as exc:  # noqa: BLE001 - library raises broad types
        raise ValueError(f"id_token verification failed: {exc}") from exc

    email = (claims.get("email") or "").lower()
    if not email:
        raise ValueError("Google account has no email.")
    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=email,
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"),
        picture=claims.get("picture"),
        hd=(claims.get("hd") or "").lower() or None,
    )
