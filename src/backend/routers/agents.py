"""Agents API. Epic 4: the rent entrypoint (`/checkout`). Epic 7 extends this with
list/detail/lifecycle and wires slot-assign + container deploy into the paid path."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import Agent, User
from backend.dependencies import current_user, db_session, get_billing, get_settings_dep
from backend.providers.base import BillingProvider
from backend.schemas.agents import CheckoutIn, CheckoutOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/checkout", response_model=CheckoutOut)
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
    await session.flush()  # need agent.id as the checkout client_reference_id

    cs = await billing.create_checkout(
        client_reference_id=agent.id,
        email=user.email,
        success_url=f"{settings.frontend_base_url}/dashboard?checkout=success",
        cancel_url=f"{settings.frontend_base_url}/dashboard?checkout=cancel",
    )
    return CheckoutOut(agent_id=agent.id, checkout_url=cs.url)
