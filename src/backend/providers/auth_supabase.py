"""SupabaseAuth — real OAuth via Supabase Auth (GitHub/Google). Credential-gated;
exercised only when SUPABASE_URL/keys are set (contract test skips otherwise).
The `supabase` import is lazy so mock mode never requires the SDK."""

from __future__ import annotations

from urllib.parse import urlencode

from backend.config import Settings
from backend.providers.base import AuthProvider, ExternalIdentity, ProviderError


class SupabaseAuth(AuthProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise ProviderError("SupabaseAuth requires SUPABASE_URL + SUPABASE_ANON_KEY")
        self._url = settings.supabase_url.rstrip("/")
        self._anon_key = settings.supabase_anon_key

    def authorize_url(self, *, provider: str, state: str, redirect_uri: str) -> str:
        q = urlencode({"provider": provider, "redirect_to": f"{redirect_uri}?state={state}"})
        return f"{self._url}/auth/v1/authorize?{q}"

    async def exchange(self, *, code: str, redirect_uri: str) -> ExternalIdentity:
        from supabase import create_client  # lazy: real-mode only

        client = create_client(self._url, self._anon_key)
        session = client.auth.exchange_code_for_session({"auth_code": code})
        user = session.user
        identities = getattr(user, "identities", None) or []
        provider = identities[0].provider if identities else "supabase"
        meta = user.user_metadata or {}
        return ExternalIdentity(
            provider=provider,
            ext_id=str(user.id),
            email=user.email or meta.get("email", ""),
            username=meta.get("user_name") or meta.get("name") or (user.email or "").split("@")[0],
        )
