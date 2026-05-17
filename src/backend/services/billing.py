"""Billing event handling — idempotent (docs/ARCHITECTURE.md §5.4 / D13).

Epic 4 owns the billing-side state machine (Subscription rows, Agent status). The
slot-assign + container-deploy seam (`_provision`) is filled by Epic 7's orchestrator;
until then checkout marks the agent `paid` (awaiting provisioning)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Agent, ProcessedEvent, Subscription
from backend.providers.base import BillingEvent, BillingEventType

DUPLICATE = "duplicate"


async def _already_processed(session: AsyncSession, event_id: str) -> bool:
    if await session.get(ProcessedEvent, event_id):
        return True
    session.add(ProcessedEvent(event_id=event_id))
    return False


async def handle_event(event: BillingEvent, *, session: AsyncSession) -> str:
    """Returns an outcome string. Re-delivery of a known event id is a no-op."""
    if await _already_processed(session, event.event_id):
        return DUPLICATE

    if event.type is BillingEventType.checkout_completed:
        return await _on_checkout_completed(event, session)
    if event.type is BillingEventType.subscription_deleted:
        return await _on_subscription_deleted(event, session)
    if event.type is BillingEventType.payment_failed:
        return await _on_payment_failed(event, session)
    return "ignored"


async def _on_checkout_completed(event: BillingEvent, session: AsyncSession) -> str:
    agent = await session.get(Agent, event.client_reference_id)
    if agent is None:
        return "agent_not_found"

    today = date.today()
    period_end = (datetime.now(UTC) + timedelta(days=30)).date()
    session.add(
        Subscription(
            agent_id=agent.id,
            stripe_sub_id=event.subscription_id,
            stripe_cus_id=event.customer_id,
            status="active",
            current_period_start=today,
            current_period_end=period_end,
        )
    )
    agent.billing_period_start = today
    agent.billing_period_end = period_end
    agent.renewal_date = period_end
    # Seam: Epic 7 assigns a slot + deploys the container here, flipping to
    # "deployed". Until then the agent is paid and awaiting provisioning.
    agent.status = "paid"
    return "paid"


async def _on_subscription_deleted(event: BillingEvent, session: AsyncSession) -> str:
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.stripe_sub_id == event.subscription_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        return "subscription_not_found"
    sub.status = "canceled"
    agent = await session.get(Agent, sub.agent_id)
    if agent and agent.status not in ("recycled", "error"):
        # Stays usable until period end; the recycle sweep (Epic 11) reclaims it.
        agent.status = "canceling"
    return "canceled"


async def _on_payment_failed(event: BillingEvent, session: AsyncSession) -> str:
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.stripe_sub_id == event.subscription_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        return "subscription_not_found"
    sub.status = "past_due"
    agent = await session.get(Agent, sub.agent_id)
    if agent:
        agent.status = "error"
    return "payment_failed"
