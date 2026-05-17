"""`make seed` — 1 fake VPS + N available slots + one admin user. Idempotent:
re-running tops the pool up to N and never duplicates the admin.

Slots are pre-spawned permanent infra (PRD §2.1): names hermesagent1..N, URLs
immutable after creation. In mock mode vps_ip is loopback (LocalDockerProvisioner
maps slot→local container port at deploy time)."""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from backend.config import Settings, get_settings
from backend.db.fleet_models import AgentSlot, VpsServer
from backend.db.models import User
from backend.db.session import Database, get_db


async def seed(db: Database, settings: Settings) -> dict[str, int]:
    await db.create_all()
    async with db.sessionmaker() as s:
        # Admin user (mock identity) — idempotent on (provider, ext_id).
        admin = (
            await s.execute(select(User).where(User.provider == "mock", User.ext_id == "admin"))
        ).scalar_one_or_none()
        if admin is None:
            s.add(
                User(
                    provider="mock",
                    ext_id="admin",
                    email=settings.mock_oauth_email,
                    username="admin",
                    is_admin=True,
                )
            )

        # One fake VPS.
        vps = (
            await s.execute(select(VpsServer).where(VpsServer.name == "vps-local-1"))
        ).scalar_one_or_none()
        if vps is None:
            vps = VpsServer(
                name="vps-local-1",
                ip_address="127.0.0.1",
                location="local",
                slots_total=settings.fleet_seed_slots,
                slots_free=settings.fleet_seed_slots,
            )
            s.add(vps)
            await s.flush()  # need vps.id

        domain = settings.agents_domain
        created = 0
        for i in range(1, settings.fleet_seed_slots + 1):
            name = f"hermesagent{i}"
            if (await s.get(AgentSlot, name)) is not None:
                continue
            s.add(
                AgentSlot(
                    slot_name=name,
                    vps_id=vps.id,
                    slot_index=i - 1,
                    status="available",
                    a2a_url=f"https://{domain}/{name}/a2a",
                    ws_url=f"https://{domain}/{name}/ws",
                    vps_ip=vps.ip_address,
                )
            )
            created += 1
        await s.commit()

    async with db.sessionmaker() as s:
        total = (await s.execute(select(func.count()).select_from(AgentSlot))).scalar_one()
        available = (
            await s.execute(
                select(func.count()).select_from(AgentSlot).where(AgentSlot.status == "available")
            )
        ).scalar_one()
    return {"slots_total": total, "slots_available": available, "slots_created": created}


async def _main() -> None:
    settings = get_settings()
    result = await seed(get_db(settings), settings)
    print(f"[seed] {result}")


if __name__ == "__main__":
    asyncio.run(_main())
