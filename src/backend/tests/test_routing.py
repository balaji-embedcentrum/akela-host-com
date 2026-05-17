"""Epic 7.2: the Traefik HTTP-provider endpoint emits live routes for assigned
slots (ARCHITECTURE §4.3)."""

from __future__ import annotations

from urllib.parse import urlparse


def test_traefik_dynamic_reflects_assigned_slots(harness):
    c = harness.client
    # No agents yet → empty routing table.
    empty = c.get("/api/routing/traefik").json()
    assert empty["http"]["routers"] == {}

    # Rent + deploy one agent.
    harness.login()
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    cfg = c.get("/api/routing/traefik").json()
    routers = cfg["http"]["routers"]
    services = cfg["http"]["services"]

    a2a = next(k for k in routers if k.endswith("-a2a"))
    ws = next(k for k in routers if k.endswith("-ws"))
    assert "PathPrefix(`/" in routers[a2a]["rule"]
    assert services[a2a]["loadBalancer"]["servers"][0]["url"].endswith(":9000")
    assert services[ws]["loadBalancer"]["servers"][0]["url"].endswith(":8766")
