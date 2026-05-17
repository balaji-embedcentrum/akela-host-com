"""Billing webhooks + the mock-pay shim. Both the real Stripe webhook and the
local mock-pay redirect funnel into one idempotent handler, then trigger the
rent→deploy orchestration on first `paid` (ARCHITECTURE §5.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import Agent, Subscription, User
from backend.dependencies import (
    db_session,
    get_billing,
    get_email,
    get_fleet,
    get_provisioner,
    get_settings_dep,
)
from backend.providers.base import (
    AgentProvisioner,
    BillingEvent,
    BillingProvider,
    EmailProvider,
    FleetRegistry,
    WebhookVerificationError,
)
from backend.providers.billing_fake import FakeBilling
from backend.services import notifications
from backend.services.billing import handle_event
from backend.services.provisioning import provision_paid_agent

router = APIRouter(tags=["billing"])


async def _finalize(
    outcome: str,
    event: BillingEvent,
    *,
    session: AsyncSession,
    fleet: FleetRegistry,
    provisioner: AgentProvisioner,
    email: EmailProvider,
) -> str:
    """On first `paid`: claim a slot + deploy + notify. On `payment_failed`:
    notify offline. Idempotent — `handle_event` yields each outcome once (D13)."""
    if outcome == "payment_failed" and event.subscription_id:
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.stripe_sub_id == event.subscription_id)
            )
        ).scalar_one_or_none()
        if sub:
            agent = await session.get(Agent, sub.agent_id)
            user = await session.get(User, agent.user_id) if agent else None
            if agent and user:
                await notifications.send_offline(email, to=user.email, agent=agent)
        return outcome

    if outcome != "paid" or not event.client_reference_id:
        return outcome
    agent = await session.get(Agent, event.client_reference_id)
    if agent is None:
        return outcome
    status = await provision_paid_agent(
        agent, session=session, fleet=fleet, provisioner=provisioner
    )
    if status == "deployed":
        user = await session.get(User, agent.user_id)
        if user:
            n_agents = (
                await session.execute(
                    select(func.count()).select_from(Agent).where(Agent.user_id == user.id)
                )
            ).scalar_one()
            if n_agents == 1:
                await notifications.send_welcome(email, to=user.email, username=user.username)
            await notifications.send_agent_deployed(email, to=user.email, agent=agent)
    return status


@router.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
    email: EmailProvider = Depends(get_email),
) -> dict[str, str]:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        event = billing.parse_webhook(headers=headers, body=body)
    except WebhookVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "signature verification failed") from exc
    outcome = await handle_event(event, session=session)
    # Commit billing state (incl. the idempotency row) before provisioning: makes
    # de-dup durable even if provisioning fails, and releases the SQLite writer
    # lock so the fleet registry's own connection can claim a slot.
    await session.commit()
    final = await _finalize(
        outcome, event, session=session, fleet=fleet, provisioner=provisioner, email=email
    )
    return {"received": "true", "outcome": final}


@router.get("/api/billing/mock-pay")
async def mock_pay(
    cs: str,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
    email: EmailProvider = Depends(get_email),
) -> RedirectResponse:
    """Stand-in for Stripe Checkout success — drives the real path end to end."""
    if not isinstance(billing, FakeBilling):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mock-pay is mock-mode only")
    event = billing.make_event(cs)
    outcome = await handle_event(event, session=session)
    await session.commit()  # see stripe_webhook — durable de-dup + release SQLite lock
    final = await _finalize(
        outcome, event, session=session, fleet=fleet, provisioner=provisioner, email=email
    )
    return RedirectResponse(
        f"{settings.frontend_base_url}/dashboard?checkout={final}",
        status_code=status.HTTP_302_FOUND,
    )
