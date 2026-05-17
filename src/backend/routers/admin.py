"""Admin panel API — all routes `require_admin`. System overview, per-VPS health
(derived from slots), per-agent + user tables, and force actions on ANY agent
(docs/ARCHITECTURE.md §4.6 / PRD §4.6)."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Agent, User
from backend.dependencies import (
    db_session,
    get_email,
    get_fleet,
    get_provisioner,
    require_admin,
)
from backend.providers.base import (
    AgentProvisioner,
    EmailProvider,
    FleetRegistry,
    ProviderError,
)
from backend.services import sweeps
from backend.services.provisioning import recycle_agent

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview(
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
) -> dict:
    slots = await fleet.list_slots()
    by_status: dict[str, int] = defaultdict(int)
    for s in slots:
        by_status[s.status.value] += 1
    users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    agents = (await session.execute(select(func.count()).select_from(Agent))).scalar_one()
    return {
        "slots": {
            "total": len(slots),
            "available": by_status.get("available", 0),
            "assigned": by_status.get("assigned", 0),
            "recycling": by_status.get("recycling", 0),
            "error": by_status.get("error", 0),
        },
        "users": users,
        "agents": agents,
    }


@router.get("/vps")
async def vps_health(fleet: FleetRegistry = Depends(get_fleet)) -> list[dict]:
    """Per-VPS rollup derived from slot rows (no slot internals leaked)."""
    slots = await fleet.list_slots()
    agg: dict[str, dict] = {}
    for s in slots:
        v = agg.setdefault(
            s.vps_id, {"vps_id": s.vps_id, "vps_ip": s.vps_ip, "total": 0, "available": 0}
        )
        v["total"] += 1
        if s.status.value == "available":
            v["available"] += 1
    return list(agg.values())


@router.get("/agents")
async def all_agents(session: AsyncSession = Depends(db_session)) -> list[dict]:
    rows = (
        await session.execute(
            select(Agent, User.email)
            .join(User, User.id == Agent.user_id)
            .order_by(Agent.created_at)
        )
    ).all()
    return [
        {
            "id": a.id,
            "display_name": a.display_name,
            "status": a.status,
            "slot_name": a.slot_name,
            "owner": email,
        }
        for a, email in rows
    ]


@router.get("/users")
async def all_users(session: AsyncSession = Depends(db_session)) -> list[dict]:
    rows = (
        await session.execute(
            select(User, func.count(Agent.id))
            .outerjoin(Agent, Agent.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at)
        )
    ).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "is_admin": u.is_admin,
            "agents": n,
        }
        for u, n in rows
    ]


@router.post("/sweeps/run")
async def run_sweeps(
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
    email: EmailProvider = Depends(get_email),
) -> dict:
    """Manually run the maintenance sweeps (normally cron-driven)."""
    recycled = await sweeps.recycle_due(session, fleet=fleet, provisioner=provisioner, email=email)
    reminded = await sweeps.renewal_reminders(session, email=email)
    orphans = await sweeps.find_orphans(session, fleet=fleet)
    return {"recycled": recycled, "reminded": reminded, "orphans": orphans}


@router.post("/agents/{agent_id}/{action}")
async def force_action(
    agent_id: str,
    action: str,
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
) -> dict:
    """action ∈ {stop, start, restart, wipe, recycle}. Works on ANY agent."""
    if action not in {"stop", "start", "restart", "wipe", "recycle"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown action")
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")

    slot = await fleet.get_slot(agent.slot_name) if agent.slot_name else None
    try:
        if action == "recycle":
            await recycle_agent(agent, fleet=fleet, provisioner=provisioner)
        elif slot is not None and action == "stop":
            await provisioner.stop(slot)
            agent.status = "stopped"
        elif slot is not None and action == "start":
            await provisioner.start(slot)
            agent.status = "deployed"
        elif slot is not None and action == "restart":
            await provisioner.stop(slot)
            await provisioner.start(slot)
            agent.status = "deployed"
        elif slot is not None and action == "wipe":
            # Wipe data + container but keep the slot assigned to the owner.
            await provisioner.recycle(slot)
            agent.status = "stopped"
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{action} failed") from exc
    return {"id": agent.id, "status": agent.status, "action": action}
