"""Epic 8: public fleet-stats endpoint (landing widget) — no auth, no internals,
reflects assignments."""

from __future__ import annotations

from urllib.parse import urlparse


def test_stats_public_and_decrements_on_rent(harness):
    c = harness.client
    s0 = c.get("/api/fleet/stats").json()  # no auth required
    assert s0 == {"available": 5, "total": 5}

    harness.login()
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    s1 = c.get("/api/fleet/stats").json()
    assert s1["total"] == 5 and s1["available"] == 4  # one slot now assigned
