"""Epic 13 AC: usage = sum of prorated billable agents minus referral credit (D16)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from backend.db.models import Agent
from backend.services.proration import first_period_cents
from backend.services.usage import compute_usage


def _agent(status: str, start: date, cents: int = 400) -> Agent:
    return Agent(
        id=f"a-{start}-{status}",
        user_id="u1",
        display_name="x",
        status=status,
        monthly_cost_cents=cents,
        billing_period_start=start,
    )


def test_compute_usage_proration_credit_and_filtering():
    today = date(2026, 4, 16)  # April: 30 days → 15/30
    started_this_month = _agent("deployed", date(2026, 4, 16))  # prorated → 200
    started_earlier = _agent("stopped", date(2026, 3, 1))  # full → 400
    not_billable = _agent("recycled", date(2026, 4, 1))  # excluded

    u = compute_usage([started_this_month, started_earlier, not_billable], 0, today)
    assert len(u.items) == 2
    assert u.subtotal_cents == 200 + 400
    assert u.total_cents == 600

    # Credit is applied and floored at the subtotal.
    u2 = compute_usage([started_this_month], 100_00, today)
    assert u2.credit_cents == 200 and u2.total_cents == 0


async def test_usage_endpoint(harness):
    harness.login()
    c = harness.client
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    u = c.get("/api/billing/usage").json()
    assert len(u["items"]) == 1
    assert u["items"][0]["display_name"] == "raj"
    assert u["subtotal_cents"] == first_period_cents(400, date.today())
    assert u["total_cents"] == u["subtotal_cents"]  # no credit yet
    assert u["credit_cents"] == 0
