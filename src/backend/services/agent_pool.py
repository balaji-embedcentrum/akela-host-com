"""Slot pool service — claim an available slot atomically, retrying on the lost
race so two concurrent rents always land on different slots (ARCHITECTURE §5.1)."""

from __future__ import annotations

from backend.providers.base import FleetRegistry, Slot, SlotUnavailable


async def claim_slot(
    fleet: FleetRegistry, *, user_id: str, api_key_hash: str, retries: int = 8
) -> Slot:
    """Returns a freshly-assigned Slot, or raises SlotUnavailable if the pool is
    exhausted (or every attempt lost the atomic claim race)."""
    for _ in range(retries):
        candidate = await fleet.get_available_slot()
        if candidate is None:
            raise SlotUnavailable("agent pool exhausted")
        try:
            return await fleet.assign_slot(candidate.slot_name, user_id, api_key_hash)
        except SlotUnavailable:
            continue  # another rent won this slot — try the next one
    raise SlotUnavailable("could not claim a slot after retries")
