"""StripeBilling — real Stripe Subscriptions. Credential-gated; `stripe` is lazy
imported so mock mode never needs the SDK (architecture rule)."""

from __future__ import annotations

from backend.config import Settings
from backend.providers.base import (
    BillingEvent,
    BillingEventType,
    BillingProvider,
    CheckoutSession,
    ProviderError,
    WebhookVerificationError,
)

_TYPE_MAP = {
    "checkout.session.completed": BillingEventType.checkout_completed,
    "customer.subscription.deleted": BillingEventType.subscription_deleted,
    "invoice.payment_failed": BillingEventType.payment_failed,
}


class StripeBilling(BillingProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.stripe_secret_key or not settings.stripe_price_id:
            raise ProviderError("StripeBilling requires STRIPE_SECRET_KEY + STRIPE_PRICE_ID")
        self._secret = settings.stripe_secret_key
        self._price = settings.stripe_price_id
        self._webhook_secret = settings.stripe_webhook_secret

    def _client(self):
        import stripe  # lazy: real-mode only

        stripe.api_key = self._secret
        return stripe

    async def create_checkout(
        self, *, client_reference_id: str, email: str, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        stripe = self._client()
        s = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": self._price, "quantity": 1}],
            client_reference_id=client_reference_id,
            customer_email=email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSession(id=s.id, url=s.url, customer_ref=s.customer)

    def parse_webhook(self, *, headers: dict, body: bytes) -> BillingEvent:
        stripe = self._client()
        sig = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(body, sig, self._webhook_secret)
        except Exception as exc:  # stripe.error.SignatureVerificationError etc.
            raise WebhookVerificationError(str(exc)) from exc
        obj = event["data"]["object"]
        return BillingEvent(
            type=_TYPE_MAP.get(event["type"], BillingEventType.unknown),
            event_id=event["id"],
            customer_id=obj.get("customer"),
            subscription_id=obj.get("subscription") or obj.get("id"),
            client_reference_id=obj.get("client_reference_id"),
            raw=dict(event),
        )

    async def cancel_subscription(self, subscription_id: str) -> None:
        stripe = self._client()
        stripe.Subscription.delete(subscription_id)
