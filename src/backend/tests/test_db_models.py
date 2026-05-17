"""Epic 2: ORM models persist and relate correctly across both metadatas (SQLite,
fleet schema translated)."""

from __future__ import annotations

from sqlalchemy import select

from backend.db.fleet_models import AgentSlot, VpsServer
from backend.db.models import Agent, Subscription, User


async def test_web_models_roundtrip(db):
    async with db.sessionmaker() as s:
        user = User(provider="mock", ext_id="u1", email="u@x.com", username="u")
        s.add(user)
        await s.flush()
        agent = Agent(user_id=user.id, display_name="raj-alpha", slot_name="hermesagent1")
        s.add(agent)
        await s.flush()
        s.add(Subscription(agent_id=agent.id, stripe_sub_id="sub_1", status="active"))
        await s.commit()

    async with db.sessionmaker() as s:
        got = (await s.execute(select(Agent).where(Agent.slot_name == "hermesagent1"))).scalar_one()
        assert got.user.email == "u@x.com"
        assert got.subscription is not None
        assert got.subscription.stripe_sub_id == "sub_1"
        assert got.monthly_cost_cents == 400  # default
        assert got.status == "pending"


async def test_fleet_models_roundtrip(db):
    async with db.sessionmaker() as s:
        vps = VpsServer(name="vps-1", ip_address="10.0.0.1", slots_total=2, slots_free=2)
        s.add(vps)
        await s.flush()
        s.add(
            AgentSlot(
                slot_name="hermesagent1",
                vps_id=vps.id,
                status="available",
                a2a_url="https://x/hermesagent1/a2a",
                ws_url="https://x/hermesagent1/ws",
                vps_ip=vps.ip_address,
            )
        )
        await s.commit()

    async with db.sessionmaker() as s:
        slot = await s.get(AgentSlot, "hermesagent1")
        assert slot is not None
        assert slot.status == "available"
        assert slot.ram_limit_bytes == 1073741824  # 1 GiB default
