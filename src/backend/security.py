"""Session JWT + OAuth state token + agent API key hashing. No external SDK here —
pyjwt/bcrypt are stdlib-like crypto libs, not provider integrations."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

SESSION_COOKIE = "akela_session"
_ALG = "HS256"
_SESSION_TTL = timedelta(days=7)
_STATE_TTL = timedelta(minutes=15)


def issue_session(secret: str, *, user_id: str, email: str, is_admin: bool) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "is_admin": is_admin,
            "iat": now,
            "exp": now + _SESSION_TTL,
            "typ": "session",
        },
        secret,
        algorithm=_ALG,
    )


def read_session(secret: str, token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on invalid/expired/forged token."""
    claims = jwt.decode(token, secret, algorithms=[_ALG])
    if claims.get("typ") != "session":
        raise jwt.InvalidTokenError("not a session token")
    return claims


def issue_state(secret: str, *, redirect: str, provider: str, ref: str | None = None) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "redirect": redirect,
            "provider": provider,
            "ref": ref or "",
            "nonce": secrets.token_urlsafe(8),
            "iat": now,
            "exp": now + _STATE_TTL,
            "typ": "oauth_state",
        },
        secret,
        algorithm=_ALG,
    )


def read_state(secret: str, token: str) -> dict[str, Any]:
    claims = jwt.decode(token, secret, algorithms=[_ALG])
    if claims.get("typ") != "oauth_state":
        raise jwt.InvalidTokenError("not a state token")
    return claims


def generate_api_key() -> str:
    """The agent bearer token (PRD AKELA_API_KEY). Shown to the user once."""
    return "akela_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(api_key: str, hashed: str) -> bool:
    return bcrypt.checkpw(api_key.encode(), hashed.encode())
