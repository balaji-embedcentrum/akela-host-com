"""Epic 12 AC: mid-month rent is prorated; 1st-of-month = full price (D15)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from sqlalchemy import select

from backend.db.models import Subscription
from backend.services.proration import first_period_cents


def test_formula():
    assert first_period_cents(400, date(2026, 5, 1)) == 400  # 1st → full month
    assert first_period_cents(400, date(2026, 4, 16)) == 200  # 15/30 days
    assert first_period_cents(400, date(2026, 5, 31)) == 13  # 1/31 days
    assert first_period_cents(400, date(2026, 2, 15)) == 200  # 14/28 → 200


async def test_checkout_and_subscription_carry_proration(harness):
    harness.login()
    c = harness.client
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()

    expected = first_period_cents(400, date.today())
    assert out["first_period_cents"] == expected

    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    async with harness.db.sessionmaker() as s:
        sub = (
            await s.execute(select(Subscription).where(Subscription.agent_id == out["agent_id"]))
        ).scalar_one()
    assert sub.first_period_cents == expected
