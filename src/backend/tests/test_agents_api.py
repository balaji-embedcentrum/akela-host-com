"""Epic 7 AC: rent → deploy → detail(api_key once) → stop/start → redeploy →
cancel → recycle, all via the API in local mode (FakeProvisioner, seeded pool)."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import func, select

from backend.db.fleet_models import AgentSlot


def _rent_and_pay(h) -> str:
    h.login()
    out = h.client.post("/api/agents/checkout", json={"display_name": "raj-alpha"}).json()
    pay = urlparse(out["checkout_url"])
    r = h.client.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    assert "checkout=deployed" in r.headers["location"]
    return out["agent_id"]


async def test_full_agent_lifecycle(harness):
    c = harness.client
    agent_id = _rent_and_pay(harness)

    # list — no api_key ever here
    agents = c.get("/api/agents").json()
    assert len(agents) == 1
    assert agents[0]["status"] == "deployed"
    assert agents[0]["api_key"] is None
    assert agents[0]["slot_name"]

    # detail — api_key shown exactly once, then nulled
    d1 = c.get(f"/api/agents/{agent_id}").json()
    assert d1["api_key"] and d1["api_key"].startswith("akela_")
    assert d1["a2a_url"] and d1["workspace_url"]
    d2 = c.get(f"/api/agents/{agent_id}").json()
    assert d2["api_key"] is None

    # rename
    assert (
        c.patch(f"/api/agents/{agent_id}", json={"display_name": "renamed"}).json()["display_name"]
        == "renamed"
    )

    # stop / start
    assert c.post(f"/api/agents/{agent_id}/stop").json()["status"] == "stopped"
    assert c.post(f"/api/agents/{agent_id}/start").json()["status"] == "deployed"

    # redeploy with config (secrets passed through, never persisted)
    r = c.post(f"/api/agents/{agent_id}/redeploy", json={"env": {"OPENROUTER_API_KEY": "x"}})
    assert r.status_code == 200 and r.json()["status"] == "deployed"

    # cancel → recycle, slot returns to the pool
    assert c.post(f"/api/agents/{agent_id}/cancel").json()["status"] == "recycled"
    async with harness.db.sessionmaker() as s:
        avail = (
            await s.execute(
                select(func.count()).select_from(AgentSlot).where(AgentSlot.status == "available")
            )
        ).scalar_one()
    assert avail == 5  # all slots free again (pool size 5)


def test_ownership_enforced(harness):
    harness.login()
    assert harness.client.get("/api/agents/not-mine").status_code == 404


def test_checkout_requires_auth(harness):
    assert (
        harness.client.post("/api/agents/checkout", json={"display_name": "x"}).status_code == 401
    )
