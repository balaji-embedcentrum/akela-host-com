"""Billing webhooks + the mock-pay shim. Both the real Stripe webhook and the
local mock-pay redirect funnel into one idempotent handler, then trigger the
rent→deploy orchestration on first `paid` (ARCHITECTURE §5.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.db.models import Agent
from backend.dependencies import (
    db_session,
    get_billing,
    get_fleet,
    get_provisioner,
    get_settings_dep,
)
from backend.providers.base import (
    AgentProvisioner,
    BillingEvent,
    BillingProvider,
    FleetRegistry,
    WebhookVerificationError,
)
from backend.providers.billing_fake import FakeBilling
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
) -> str:
    """On the first `paid` outcome, claim a slot + deploy. Idempotent because
    `handle_event` only returns `paid` once per event id (D13)."""
    if outcome != "paid" or not event.client_reference_id:
        return outcome
    agent = await session.get(Agent, event.client_reference_id)
    if agent is None:
        return outcome
    return await provision_paid_agent(agent, session=session, fleet=fleet, provisioner=provisioner)


@router.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
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
    final = await _finalize(outcome, event, session=session, fleet=fleet, provisioner=provisioner)
    return {"received": "true", "outcome": final}


@router.get("/api/billing/mock-pay")
async def mock_pay(
    cs: str,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
    fleet: FleetRegistry = Depends(get_fleet),
    provisioner: AgentProvisioner = Depends(get_provisioner),
) -> RedirectResponse:
    """Stand-in for Stripe Checkout success — drives the real path end to end."""
    if not isinstance(billing, FakeBilling):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mock-pay is mock-mode only")
    event = billing.make_event(cs)
    outcome = await handle_event(event, session=session)
    await session.commit()  # see stripe_webhook — durable de-dup + release SQLite lock
    final = await _finalize(outcome, event, session=session, fleet=fleet, provisioner=provisioner)
    return RedirectResponse(
        f"{settings.frontend_base_url}/dashboard?checkout={final}",
        status_code=status.HTTP_302_FOUND,
    )
