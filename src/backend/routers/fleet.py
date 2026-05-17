"""Public fleet-availability stats (landing page widget, PRD §4.1). No auth, no
slot internals exposed — just counts."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.dependencies import get_fleet
from backend.providers.base import FleetRegistry, SlotStatus

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/stats")
async def fleet_stats(fleet: FleetRegistry = Depends(get_fleet)) -> dict[str, int]:
    slots = await fleet.list_slots()
    available = sum(1 for s in slots if s.status is SlotStatus.available)
    return {"available": available, "total": len(slots)}
