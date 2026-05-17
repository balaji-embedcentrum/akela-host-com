"""Scheduled maintenance (docs/ARCHITECTURE.md §5.2, PRD §2). Pure functions —
runnable from a cron, the admin trigger, or a test. Idempotent and best-effort.

- recycle_due:   cancelled/past-due agents past their billing period → recycle
- renewal_reminders: agents renewing in 3 days → email
- find_orphans:  consistency check (assigned slot w/o live agent, or vice-versa)
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Agent, AgentHealthSample, User
from backend.providers.base import AgentProvisioner, EmailProvider, FleetRegistry, SlotStatus
from backend.services import notifications
from backend.services.provisioning import recycle_agent

_LIVE = {"deployed", "stopped", "paid", "error", "canceling"}


async def recycle_due(
    session: AsyncSession,
    *,
    fleet: FleetRegistry,
    provisioner: AgentProvisioner,
    email: EmailProvider,
    today: date | None = None,
) -> list[str]:
    """Recycle agents whose rental has lapsed (cancelled and period ended).
    Returns the ids recycled."""
    today = today or date.today()
    rows = (
        (
            await session.execute(
                select(Agent).where(
                    Agent.status == "canceling",
                    Agent.billing_period_end.is_not(None),
                    Agent.billing_period_end <= today,
                )
            )
        )
        .scalars()
        .all()
    )
    recycled: list[str] = []
    for agent in rows:
        await recycle_agent(agent, fleet=fleet, provisioner=provisioner)
        user = await session.get(User, agent.user_id)
        if user:
            await notifications.send_recycled(email, to=user.email, agent=agent)
        recycled.append(agent.id)
    return recycled


async def renewal_reminders(
    session: AsyncSession, *, email: EmailProvider, today: date | None = None
) -> list[str]:
    today = today or date.today()
    target = today + timedelta(days=3)
    rows = (
        (
            await session.execute(
                select(Agent).where(Agent.status == "deployed", Agent.renewal_date == target)
            )
        )
        .scalars()
        .all()
    )
    notified: list[str] = []
    for agent in rows:
        user = await session.get(User, agent.user_id)
        if user:
            await notifications.send_renewal_reminder(email, to=user.email, agent=agent)
            notified.append(agent.id)
    return notified


async def find_orphans(session: AsyncSession, *, fleet: FleetRegistry) -> dict[str, list[str]]:
    """Cross-store consistency check (the link is logical, not an FK — D-note)."""
    assigned = {s.slot_name for s in await fleet.list_slots(SlotStatus.assigned)}
    live_agents = (
        (await session.execute(select(Agent).where(Agent.status.in_(_LIVE)))).scalars().all()
    )
    agent_slots = {a.slot_name for a in live_agents if a.slot_name}

    return {
        # assigned slots with no live agent pointing at them
        "stranded_slots": sorted(assigned - agent_slots),
        # live agents whose slot isn't actually assigned in the registry
        "dangling_agents": sorted(
            a.id for a in live_agents if a.slot_name and a.slot_name not in assigned
        ),
    }


async def sample_health(
    session: AsyncSession, *, fleet: FleetRegistry, provisioner: AgentProvisioner
) -> int:
    """Probe each assigned slot and record one health sample per live agent
    (feeds uptime %, D17). Returns the number of samples written."""
    n = 0
    for slot in await fleet.list_slots(SlotStatus.assigned):
        agent = (
            await session.execute(
                select(Agent).where(Agent.slot_name == slot.slot_name, Agent.status.in_(_LIVE))
            )
        ).scalar_one_or_none()
        if agent is None:
            continue
        st = await provisioner.status(slot)
        session.add(AgentHealthSample(agent_id=agent.id, healthy=bool(st.running)))
        n += 1
    return n
