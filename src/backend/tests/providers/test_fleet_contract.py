"""FleetRegistry contract — LocalPgFleet (always) + SupabaseFleet (creds only)."""

from __future__ import annotations

import pytest

from backend.providers.base import RouteTarget, Slot, SlotStatus, SlotUnavailable
from backend.providers.factory import build_provider

from ..conftest import has_env


@pytest.fixture
def fleet(seeded_pool):
    # mock impl over the seeded sqlite pool; real impl is creds-gated below.
    return build_provider("fleet", seeded_pool)


async def test_get_available_then_assign_then_unassign(fleet):
    slot = await fleet.get_available_slot()
    assert isinstance(slot, Slot) and slot.status is SlotStatus.available

    assigned = await fleet.assign_slot(slot.slot_name, "user-1", "hash-1")
    assert assigned.status is SlotStatus.assigned
    assert assigned.assigned_user_id == "user-1"

    # Re-assigning the same slot now fails (atomic claim).
    with pytest.raises(SlotUnavailable):
        await fleet.assign_slot(slot.slot_name, "user-2", "hash-2")

    await fleet.unassign_slot(slot.slot_name)
    again = await fleet.get_slot(slot.slot_name)
    assert again.status is SlotStatus.available
    assert again.assigned_user_id is None


async def test_resolve_route_and_list(fleet):
    route = await fleet.resolve_route("hermesagent1")
    assert isinstance(route, RouteTarget)
    assert route.a2a_port == 9000 and route.ws_port == 8766

    available = await fleet.list_slots(SlotStatus.available)
    assert len(available) >= 1
    assert await fleet.resolve_route("does-not-exist") is None


@pytest.mark.skipif(
    not has_env("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
    reason="no Supabase creds — real fleet skipped",
)
def test_supabase_fleet_constructs(make_settings):
    build_provider("fleet", make_settings(fleet_mode="real"))
