"""Epic 9 AC: each lifecycle event emits the right template to the sink."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from backend.db.models import Subscription


def _templates(sink: str) -> list[str]:
    p = Path(sink)
    if not p.exists():
        return []
    return [json.loads(line)["template"] for line in p.read_text().splitlines()]


def _to_addrs(sink: str) -> set[str]:
    return {json.loads(line)["to"] for line in Path(sink).read_text().splitlines()}


async def test_lifecycle_emails(harness):
    c = harness.client
    sink = harness.settings.email_sink_path

    harness.login()
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    tpls = _templates(sink)
    assert "welcome" in tpls  # first agent
    assert "agent_deployed" in tpls
    assert harness.settings.mock_oauth_email in _to_addrs(sink)

    # payment_failed → offline
    async with harness.db.sessionmaker() as s:
        sub = (
            await s.execute(select(Subscription).where(Subscription.agent_id == out["agent_id"]))
        ).scalar_one()
    body = json.dumps(
        {
            "type": "invoice.payment_failed",
            "event_id": "evt_pf_1",
            "subscription_id": sub.stripe_sub_id,
        }
    ).encode()
    c.post("/api/webhooks/stripe", content=body, headers={"x-mock-signature": "mock"})
    assert "agent_offline" in _templates(sink)

    # cancel → cancellation_confirmed + agent_recycled
    c.post(f"/api/agents/{out['agent_id']}/cancel")
    final = _templates(sink)
    assert "cancellation_confirmed" in final
    assert "agent_recycled" in final


async def test_second_agent_no_duplicate_welcome(harness):
    c = harness.client
    sink = harness.settings.email_sink_path
    harness.login()
    for name in ("a1", "a2"):
        out = c.post("/api/agents/checkout", json={"display_name": name}).json()
        pay = urlparse(out["checkout_url"])
        c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    assert _templates(sink).count("welcome") == 1  # only on the first
    assert _templates(sink).count("agent_deployed") == 2
