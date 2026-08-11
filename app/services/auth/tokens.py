"""Signed session tokens — a tiny HMAC-SHA256 JWT-alike, no extra dependencies.

Format: ``base64url(payload_json).base64url(hmac_sha256(secret, payload_bytes))``.
The payload carries the user id, email, role and an expiry. Verification is
constant-time and rejects tampered or expired tokens. Used as the value of an
httpOnly session cookie; also reused (with a short TTL) for the OAuth ``state``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


def sign(payload: dict[str, Any], secret: str, *, ttl_seconds: int) -> str:
    """Return a signed, expiring token encoding ``payload``."""
    body = dict(payload)
    body["exp"] = int(time.time()) + int(ttl_seconds)
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64e(raw)}.{_b64e(sig)}"


def verify(token: str, secret: str) -> dict[str, Any] | None:
    """Return the payload if the token is authentic and unexpired, else None."""
    if not token or not secret or "." not in token:
        return None
    try:
        body_b64, sig_b64 = token.split(".", 1)
        raw = _b64d(body_b64)
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(sig_b64)):
            return None
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
