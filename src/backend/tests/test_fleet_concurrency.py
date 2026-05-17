"""Epic 5.2: with 2 slots and 5 concurrent rents, exactly 2 succeed on distinct
slots and no slot is double-assigned (atomic claim, ARCHITECTURE §5.1)."""

from __future__ import annotations

import asyncio

from backend.db.session import get_database_for
from backend.providers.base import SlotUnavailable
from backend.providers.factory import build_provider
from backend.scripts.seed import seed
from backend.services.agent_pool import claim_slot


async def test_concurrent_claims_no_double_assign(tmp_path, make_settings):
    url = f"sqlite+aiosqlite:///{tmp_path / 'race.db'}"
    settings = make_settings(database_url=url, fleet_seed_slots=2)
    db = get_database_for(url)
    await db.create_all()
    await seed(db, settings)

    fleet = build_provider("fleet", settings)

    async def attempt(i: int):
        try:
            slot = await claim_slot(fleet, user_id=f"user-{i}", api_key_hash=f"h{i}")
            return slot.slot_name
        except SlotUnavailable:
            return None

    results = await asyncio.gather(*(attempt(i) for i in range(5)))
    won = [r for r in results if r is not None]

    assert len(won) == 2  # only as many as there are slots
    assert len(set(won)) == 2  # distinct slots — no double assignment
    assert results.count(None) == 3  # the rest correctly failed

    remaining = await fleet.get_available_slot()
    assert remaining is None  # pool fully drained
