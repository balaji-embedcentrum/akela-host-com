"""Traefik HTTP-provider endpoint. Point Traefik at GET /api/routing/traefik;
it returns live routes for every assigned slot (ARCHITECTURE §4.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.config import Settings
from backend.dependencies import get_fleet, get_settings_dep
from backend.providers.base import FleetRegistry, SlotStatus
from backend.services.routing import build_traefik_dynamic

router = APIRouter(prefix="/api/routing", tags=["routing"])


@router.get("/traefik")
async def traefik_dynamic(
    fleet: FleetRegistry = Depends(get_fleet),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    assigned = await fleet.list_slots(SlotStatus.assigned)
    return build_traefik_dynamic(assigned, settings)
