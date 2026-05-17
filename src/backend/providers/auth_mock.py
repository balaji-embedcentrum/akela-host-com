"""MockOAuth — deterministic identity, no network. authorize_url points the browser
straight back at our callback with a fake code so the whole login→session flow is
exercisable offline (docs/ARCHITECTURE.md §5.5)."""

from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from backend.config import Settings
from backend.providers.base import AuthProvider, ExternalIdentity

MOCK_CODE = "mock-auth-code"


class MockOAuth(AuthProvider):
    def __init__(self, settings: Settings) -> None:
        self._email = settings.mock_oauth_email

    def authorize_url(self, *, provider: str, state: str, redirect_uri: str) -> str:
        # No external IdP — bounce straight back to the callback.
        return f"{redirect_uri}?{urlencode({'code': MOCK_CODE, 'state': state})}"

    async def exchange(self, *, code: str, redirect_uri: str) -> ExternalIdentity:
        if code != MOCK_CODE:
            raise ValueError("invalid mock auth code")
        ext_id = hashlib.sha256(self._email.encode()).hexdigest()[:24]
        username = self._email.split("@", 1)[0]
        return ExternalIdentity(
            provider="mock", ext_id=ext_id, email=self._email, username=username
        )
