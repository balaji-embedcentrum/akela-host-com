"""Billing webhooks + the mock-pay shim. Both the real Stripe webhook and the
local mock-pay redirect funnel into one idempotent handler (ARCHITECTURE §5.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.dependencies import db_session, get_billing, get_settings_dep
from backend.providers.base import BillingProvider, WebhookVerificationError
from backend.providers.billing_fake import FakeBilling
from backend.services.billing import handle_event

router = APIRouter(tags=["billing"])


@router.post("/api/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
) -> dict[str, str]:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        event = billing.parse_webhook(headers=headers, body=body)
    except WebhookVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "signature verification failed") from exc
    outcome = await handle_event(event, session=session)
    return {"received": "true", "outcome": outcome}


@router.get("/api/billing/mock-pay")
async def mock_pay(
    cs: str,
    billing: BillingProvider = Depends(get_billing),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> RedirectResponse:
    """Stand-in for Stripe Checkout success — drives the real handler end to end."""
    if not isinstance(billing, FakeBilling):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mock-pay is mock-mode only")
    event = billing.make_event(cs)
    outcome = await handle_event(event, session=session)
    return RedirectResponse(
        f"{settings.frontend_base_url}/dashboard?checkout={outcome}",
        status_code=status.HTTP_302_FOUND,
    )
