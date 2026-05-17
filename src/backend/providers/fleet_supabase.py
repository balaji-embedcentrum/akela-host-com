"""SupabaseFleet — real FleetRegistry via private Supabase Edge Functions
(docs/ARCHITECTURE.md §2.1). Credential-gated; contract test skips without creds.
Uses httpx (generic HTTP) against the edge endpoints with the service-role key."""

from __future__ import annotations

import httpx

from backend.config import Settings
from backend.providers.base import (
    FleetRegistry,
    ProviderError,
    RouteTarget,
    Slot,
    SlotStatus,
    SlotUnavailable,
)


class SupabaseFleet(FleetRegistry):
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ProviderError("SupabaseFleet requires SUPABASE_URL + service role key")
        self._base = settings.supabase_url.rstrip("/") + "/functions/v1/slot-registry"
        self._key = settings.supabase_service_role_key
        self._a2a_port = settings.agent_a2a_port
        self._ws_port = settings.agent_workspace_port

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "apikey": self._key}

    def _slot(self, d: dict) -> Slot:
        return Slot(
            slot_name=d["slot_name"],
            vps_id=d["vps_id"],
            vps_ip=d["vps_ip"],
            status=SlotStatus(d.get("status", "assigned")),
            a2a_url=d["a2a_url"],
            ws_url=d["ws_url"],
            a2a_port=self._a2a_port,
            ws_port=self._ws_port,
            assigned_user_id=d.get("assigned_user_id"),
        )

    async def get_available_slot(self) -> Slot | None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._base}/slot/available", params={"count": 1}, headers=self._headers()
            )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        return self._slot(data) if data else None

    async def assign_slot(self, slot_name: str, user_id: str, api_key_hash: str) -> Slot:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self._base}/slot/assign",
                json={"slot_name": slot_name, "user_id": user_id, "api_key_hash": api_key_hash},
                headers=self._headers(),
            )
        if r.status_code == 409:
            raise SlotUnavailable(f"slot {slot_name} was not available")
        r.raise_for_status()
        return self._slot(r.json())

    async def unassign_slot(self, slot_name: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self._base}/slot/unassign",
                json={"slot_name": slot_name},
                headers=self._headers(),
            )
        r.raise_for_status()

    async def get_slot(self, slot_name: str) -> Slot | None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/slot/{slot_name}", headers=self._headers())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return self._slot(r.json())

    async def resolve_route(self, slot_name: str) -> RouteTarget | None:
        slot = await self.get_slot(slot_name)
        if slot is None:
            return None
        return RouteTarget(slot.slot_name, slot.vps_ip, slot.a2a_port, slot.ws_port)

    async def list_slots(self, status: SlotStatus | None = None) -> list[Slot]:
        params = {"status": status.value} if status else {}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/slots", params=params, headers=self._headers())
        r.raise_for_status()
        return [self._slot(d) for d in r.json()]
