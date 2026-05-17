"""Agents API — rent (checkout), list, detail (api_key shown once), rename,
stop/start, redeploy (config upload), cancel→recycle. Ownership enforced on
every per-agent route (docs/ARCHITECTURE.md §5)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import Agent, Subscription, User
from backend.dependencies import (
    current_user,
    db_session,
    get_billing,
    get_email,
    get_fleet,
    get_provisioner,
    get_settings_dep,
)
from backend.providers.base import (
    AgentProvisioner,
    BillingProvider,
    EmailProvider,
    FleetRegistry,
    ProviderError,
)
from backend.ratelimit import RateLimit
from backend.schemas.agents import AgentOut, CheckoutIn, CheckoutOut, RedeployIn, RenameIn
from backend.services import notifications
from backend.services.proration import first_period_cents
from backend.services.provisioning import recycle_agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def _owned(agent_id: str, user: User, session: AsyncSession) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    return agent


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    dependencies=[Depends(RateLimit("checkout", 30))],
)
async def create_checkout(
    payload: CheckoutIn,
    user: User = Depends(current_user),
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> CheckoutOut:
    agent = Agent(
        user_id=user.id,
        display_name=payload.display_name,
        status="pending",
        monthly_cost_cents=settings.agent_monthly_price_cents,
    )
    session.add(agent)
    await session.flush()
    cs = await billing.create_checkout(
        client_reference_id=agent.id,
        email=user.email,
        success_url=f"{settings.frontend_base_url}/dashboard?checkout=success",
        cancel_url=f"{settings.frontend_base_url}/dashboard?checkout=cancel",
    )
    return CheckoutOut(
        agent_id=agent.id,
        checkout_url=cs.url,
        first_period_cents=first_period_cents(agent.monthly_cost_cents, date.today()),
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    user: User = Depends(current_user), session: AsyncSession = Depends(db_session)
) -> list[Agent]:
    rows = (
        (
            await session.execute(
                select(Agent).where(Agent.user_id == user.id).order_by(Agent.created_at)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> AgentOut:
    agent = await _owned(agent_id, user, session)
    out = AgentOut.model_validate(agent)
    if agent.api_key_plain:  # shown exactly once, then nulled (PRD §4.5)
        out.api_key = agent.api_key_plain
        agent.api_key_plain = None
        await session.flush()
    return out


@router.patch("/{agent_id}", response_model=AgentOut)
async def rename_agent(
    agent_id: str,
    payload: RenameIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> Agent:
    agent = await _owned(agent_id, user, session)
    agent.display_name = payload.display_name
    return agent


@router.post("/{agent_id}/stop", response_model=AgentOut)
async def stop_agent(
    agent_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
) -> Agent:
    agent = await _owned(agent_id, user, session)
    if agent.slot_name:
        slot = await fleet.get_slot(agent.slot_name)
        if slot:
            try:
                await provisioner.stop(slot)
            except ProviderError as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "stop failed") from exc
    agent.status = "stopped"
    return agent


@router.post("/{agent_id}/start", response_model=AgentOut)
async def start_agent(
    agent_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
) -> Agent:
    agent = await _owned(agent_id, user, session)
    if agent.slot_name:
        slot = await fleet.get_slot(agent.slot_name)
        if slot:
            try:
                await provisioner.start(slot)
            except ProviderError as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "start failed") from exc
    agent.status = "deployed"
    return agent


@router.post("/{agent_id}/redeploy", response_model=AgentOut)
async def redeploy_agent(
    agent_id: str,
    payload: RedeployIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
) -> Agent:
    """Upload/replace config (.env) and redeploy. Secrets are passed straight to
    the provisioner and never stored (D12)."""
    agent = await _owned(agent_id, user, session)
    if not agent.slot_name:
        raise HTTPException(status.HTTP_409_CONFLICT, "agent not provisioned yet")
    slot = await fleet.get_slot(agent.slot_name)
    if slot is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "slot missing")
    try:
        await provisioner.deploy(
            slot,
            user_env=payload.env,
            agent_api_key="",  # keep existing key; deploy reads it from running env
            display_name=agent.display_name,
        )
    except ProviderError as exc:
        agent.status = "error"
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "redeploy failed") from exc
    agent.status = "deployed"
    return agent


@router.post("/{agent_id}/cancel", response_model=AgentOut)
async def cancel_agent(
    agent_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
    billing: BillingProvider = Depends(get_billing),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
    email: EmailProvider = Depends(get_email),
) -> Agent:
    """Cancel the rental. MVP recycles immediately; the period-end deferral is
    Epic 11's scheduled sweep (PRD §2 / ToS §4)."""
    agent = await _owned(agent_id, user, session)
    sub = (
        await session.execute(select(Subscription).where(Subscription.agent_id == agent.id))
    ).scalar_one_or_none()
    if sub and sub.stripe_sub_id:
        try:
            await billing.cancel_subscription(sub.stripe_sub_id)
        except ProviderError:
            pass
    if sub:
        sub.status = "canceled"
    await notifications.send_cancellation(email, to=user.email, agent=agent)
    await recycle_agent(agent, fleet=fleet, provisioner=provisioner)
    await notifications.send_recycled(email, to=user.email, agent=agent)
    return agent
