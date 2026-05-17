"""AuthProvider contract — mock always; supabase only with credentials."""

from __future__ import annotations

import pytest

from backend.providers.base import AuthProvider, ExternalIdentity
from backend.providers.factory import build_provider

from ..conftest import has_env

AUTH_MODES = [
    "mock",
    pytest.param(
        "real",
        marks=pytest.mark.skipif(
            not has_env("SUPABASE_URL", "SUPABASE_ANON_KEY"),
            reason="no Supabase creds — real auth skipped",
        ),
    ),
]


@pytest.fixture(params=AUTH_MODES)
def auth(request, make_settings) -> AuthProvider:
    return build_provider("auth", make_settings(auth_mode=request.param))


def test_authorize_url_includes_state_and_redirect(auth):
    url = auth.authorize_url(
        provider="github", state="STATE123", redirect_uri="http://app/api/auth/callback"
    )
    assert "STATE123" in url
    assert url.startswith("http")


async def test_mock_exchange_is_deterministic(make_settings):
    provider = build_provider("auth", make_settings(auth_mode="mock"))
    from backend.providers.auth_mock import MOCK_CODE

    a = await provider.exchange(code=MOCK_CODE, redirect_uri="http://app/cb")
    b = await provider.exchange(code=MOCK_CODE, redirect_uri="http://app/cb")
    assert isinstance(a, ExternalIdentity)
    assert a == b
    assert a.provider == "mock"
    assert "@" in a.email


async def test_mock_rejects_bad_code(make_settings):
    provider = build_provider("auth", make_settings(auth_mode="mock"))
    with pytest.raises(ValueError):
        await provider.exchange(code="wrong", redirect_uri="http://app/cb")
