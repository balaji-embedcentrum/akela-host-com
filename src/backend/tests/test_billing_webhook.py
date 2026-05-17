"""Epic 4 AC: mock checkout drives the real webhook handler end to end, and the
handler is idempotent on re-delivery (D13)."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from sqlalchemy import func, select

from backend.db.models import Agent, Subscription


async def _agent(db, agent_id: str) -> Agent:
    async with db.sessionmaker() as s:
        return await s.get(Agent, agent_id)


def test_checkout_to_paid_end_to_end(harness):
    harness.login()
    c = harness.client

    r = c.post("/api/agents/checkout", json={"display_name": "raj-alpha"})
    assert r.status_code == 200
    out = r.json()
    assert out["agent_id"]
    assert "/api/billing/mock-pay" in out["checkout_url"]

    pay = urlparse(out["checkout_url"])
    r = c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    assert r.status_code == 302
    assert "checkout=paid" in r.headers["location"]


async def test_webhook_is_idempotent(harness):
    harness.login()
    c = harness.client
    out = c.post("/api/agents/checkout", json={"display_name": "raj-beta"}).json()
    pay = urlparse(out["checkout_url"])

    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    r2 = c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    assert "checkout=duplicate" in r2.headers["location"]

    agent = await _agent(harness.db, out["agent_id"])
    assert agent.status == "paid"
    async with harness.db.sessionmaker() as s:
        n = (
            await s.execute(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.agent_id == out["agent_id"])
            )
        ).scalar_one()
    assert n == 1  # not double-provisioned


def test_webhook_bad_signature_rejected(harness):
    r = harness.client.post(
        "/api/webhooks/stripe", content=b"{}", headers={"x-mock-signature": "WRONG"}
    )
    assert r.status_code == 400


async def test_payment_failed_marks_error(harness):
    harness.login()
    c = harness.client
    out = c.post("/api/agents/checkout", json={"display_name": "raj-gamma"}).json()
    pay = urlparse(out["checkout_url"])
    cs_id = pay.query.split("cs=")[1]
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    agent = await _agent(harness.db, out["agent_id"])
    async with harness.db.sessionmaker() as s:
        sub = (
            await s.execute(select(Subscription).where(Subscription.agent_id == out["agent_id"]))
        ).scalar_one()
    body = json.dumps(
        {
            "type": "invoice.payment_failed",
            "event_id": f"evt_fail_{cs_id}",
            "subscription_id": sub.stripe_sub_id,
        }
    ).encode()
    r = c.post("/api/webhooks/stripe", content=body, headers={"x-mock-signature": "mock"})
    assert r.status_code == 200 and r.json()["outcome"] == "payment_failed"
    agent = await _agent(harness.db, out["agent_id"])
    assert agent.status == "error"
