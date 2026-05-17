"""Epic 11 — the full local happy path, zero external accounts:
anon → login → rent → deploy → connect info → cancel → recycle. `make e2e`."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


def test_full_happy_path(harness):
    c = harness.client

    # 1. Anonymous: public fleet widget works, protected stuff 401.
    assert c.get("/api/fleet/stats").json() == {"available": 5, "total": 5}
    assert c.get("/api/auth/me").status_code == 401

    # 2. Sign in (offline mock OAuth).
    harness.login()
    me = c.get("/api/auth/me").json()
    assert "@" in me["email"]

    # 3. Rent → checkout → (mock) pay → provisioned.
    out = c.post("/api/agents/checkout", json={"display_name": "raj-e2e"}).json()
    agent_id = out["agent_id"]
    pay = urlparse(out["checkout_url"])
    r = c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    assert "checkout=deployed" in r.headers["location"]

    # 4. Connection info: api_key shown exactly once; URLs present.
    detail = c.get(f"/api/agents/{agent_id}").json()
    assert detail["status"] == "deployed"
    assert detail["api_key"] and detail["api_key"].startswith("akela_")
    assert detail["a2a_url"] and detail["workspace_url"]
    assert c.get(f"/api/agents/{agent_id}").json()["api_key"] is None  # gone

    # 5. The agent is routable (Traefik HTTP provider reflects it).
    routers = c.get("/api/routing/traefik").json()["http"]["routers"]
    assert any(detail["slot_name"] in k for k in routers)

    # 6. Cancel → recycle → slot back in the pool.
    assert c.post(f"/api/agents/{agent_id}/cancel").json()["status"] == "recycled"
    assert c.get("/api/fleet/stats").json()["available"] == 5

    # 7. The lifecycle emails were emitted.
    tpls = [
        json.loads(line)["template"]
        for line in Path(harness.settings.email_sink_path).read_text().splitlines()
    ]
    for t in ("welcome", "agent_deployed", "cancellation_confirmed", "agent_recycled"):
        assert t in tpls
