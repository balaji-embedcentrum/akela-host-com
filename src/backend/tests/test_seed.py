"""Epic 2 AC: `make seed` produces a rentable pool and is idempotent."""

from __future__ import annotations

from sqlalchemy import func, select

from backend.db.fleet_models import AgentSlot
from backend.db.models import User
from backend.scripts.seed import seed


async def test_seed_creates_rentable_pool(db, make_settings):
    settings = make_settings(fleet_seed_slots=7)
    result = await seed(db, settings)

    assert result == {"slots_total": 7, "slots_available": 7, "slots_created": 7}
    async with db.sessionmaker() as s:
        admin = (await s.execute(select(User).where(User.is_admin.is_(True)))).scalar_one()
        assert admin.username == "admin"
        avail = (
            await s.execute(
                select(func.count()).select_from(AgentSlot).where(AgentSlot.status == "available")
            )
        ).scalar_one()
        assert avail == 7


async def test_seed_is_idempotent(db, make_settings):
    settings = make_settings(fleet_seed_slots=5)
    await seed(db, settings)
    second = await seed(db, settings)

    assert second["slots_created"] == 0
    assert second["slots_total"] == 5
    async with db.sessionmaker() as s:
        admins = (
            await s.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
        ).scalar_one()
        assert admins == 1  # not duplicated
