"""FakeBilling — in-process Stripe. `create_checkout` returns a local mock-pay URL;
hitting it synthesizes a `checkout.session.completed` that flows through the SAME
handler the real Stripe webhook uses (docs/ARCHITECTURE.md §3.2, §5.1). No network."""

from __future__ import annotations

import json
import secrets

from backend.config import Settings
from backend.providers.base import (
    BillingEvent,
    BillingEventType,
    BillingProvider,
    CheckoutSession,
    WebhookVerificationError,
)

# Process-local store (providers are built per-request) — fine for a mock.
_CHECKOUTS: dict[str, dict[str, str]] = {}


class FakeBilling(BillingProvider):
    def __init__(self, settings: Settings) -> None:
        self._base = settings.app_base_url

    async def create_checkout(
        self, *, client_reference_id: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        cs_id = "cs_mock_" + secrets.token_urlsafe(10)
        _CHECKOUTS[cs_id] = {
            "client_reference_id": client_reference_id,
            "email": email,
            "customer": "cus_mock_" + secrets.token_urlsafe(6),
            "subscription": "sub_mock_" + secrets.token_urlsafe(6),
        }
        url = f"{self._base}/api/billing/mock-pay?cs={cs_id}"
        return CheckoutSession(id=cs_id, url=url)

    def make_event(self, cs_id: str) -> BillingEvent:
        """Synthesize the post-payment event (used by the mock-pay route)."""
        rec = _CHECKOUTS.get(cs_id)
        if rec is None:
            raise WebhookVerificationError("unknown mock checkout session")
        return BillingEvent(
            type=BillingEventType.checkout_completed,
            event_id=f"evt_{cs_id}",
            customer_id=rec["customer"],
            subscription_id=rec["subscription"],
            client_reference_id=rec["client_reference_id"],
            raw=rec,
        )

    def parse_webhook(self, *, headers: dict, body: bytes) -> BillingEvent:
        # Mock "signature": a shared static header. Real signature checking is
        # StripeBilling's job.
        if headers.get("x-mock-signature") != "mock":
            raise WebhookVerificationError("bad mock signature")
        data = json.loads(body)
        return BillingEvent(
            type=BillingEventType(data.get("type", "unknown")),
            event_id=data["event_id"],
            customer_id=data.get("customer_id"),
            subscription_id=data.get("subscription_id"),
            client_reference_id=data.get("client_reference_id"),
            raw=data,
        )

    async def cancel_subscription(self, subscription_id: str) -> None:
        return None  # nothing external to cancel
