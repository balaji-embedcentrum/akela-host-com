"""BillingProvider contract — mock always; Stripe only with credentials."""

from __future__ import annotations

import json

import pytest

from backend.providers.base import CheckoutSession, WebhookVerificationError
from backend.providers.factory import build_provider

from ..conftest import has_env

BILLING_MODES = [
    "mock",
    pytest.param(
        "real",
        marks=pytest.mark.skipif(
            not has_env("STRIPE_SECRET_KEY", "STRIPE_PRICE_ID"),
            reason="no Stripe creds — real billing skipped",
        ),
    ),
]


@pytest.fixture(params=BILLING_MODES)
def billing(request, make_settings):
    return build_provider("billing", make_settings(billing_mode=request.param))


async def test_create_checkout_returns_url(billing):
    cs = await billing.create_checkout(
        client_reference_id="agent-1",
        email="u@x.com",
        success_url="http://f/ok",
        cancel_url="http://f/no",
    )
    assert isinstance(cs, CheckoutSession)
    assert cs.id and cs.url.startswith("http")


def test_bad_signature_rejected(billing):
    with pytest.raises(WebhookVerificationError):
        billing.parse_webhook(headers={}, body=b"{}")


async def test_mock_make_event_roundtrip(make_settings):
    fake = build_provider("billing", make_settings(billing_mode="mock"))
    cs = await fake.create_checkout(
        client_reference_id="agent-9", email="u@x.com", success_url="x", cancel_url="y"
    )
    ev = fake.make_event(cs.id)
    assert ev.client_reference_id == "agent-9"
    # Same shape parses through the webhook path too.
    parsed = fake.parse_webhook(
        headers={"x-mock-signature": "mock"},
        body=json.dumps(
            {"type": ev.type.value, "event_id": ev.event_id, "client_reference_id": "agent-9"}
        ).encode(),
    )
    assert parsed.event_id == ev.event_id
