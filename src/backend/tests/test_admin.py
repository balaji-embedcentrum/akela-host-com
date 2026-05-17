"""Epic 10 AC: admin routes are admin-only and can force-recycle ANY agent."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select

from backend.db.models import User


async def _promote(harness) -> None:
    me = harness.client.get("/api/auth/me").json()
    async with harness.db.sessionmaker() as s:
        user = (await s.execute(select(User).where(User.id == me["id"]))).scalar_one()
        user.is_admin = True
        await s.commit()


def _deploy_one(h) -> str:
    out = h.client.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    h.client.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    return out["agent_id"]


def test_admin_routes_require_admin(harness):
    harness.login()
    assert harness.client.get("/api/admin/overview").status_code == 403


async def test_admin_overview_and_force_recycle(harness):
    harness.login()
    agent_id = _deploy_one(harness)
    await _promote(harness)
    c = harness.client

    ov = c.get("/api/admin/overview").json()
    assert ov["slots"]["total"] == 5
    assert ov["slots"]["assigned"] == 1
    assert ov["agents"] == 1

    agents = c.get("/api/admin/agents").json()
    assert agents[0]["id"] == agent_id
    assert "@" in agents[0]["owner"]

    users = c.get("/api/admin/users").json()
    assert any(u["is_admin"] and u["agents"] == 1 for u in users)

    vps = c.get("/api/admin/vps").json()
    assert vps[0]["total"] == 5

    # Force-recycle returns the slot to the pool.
    r = c.post(f"/api/admin/agents/{agent_id}/recycle")
    assert r.status_code == 200 and r.json()["status"] == "recycled"
    assert c.get("/api/admin/overview").json()["slots"]["available"] == 5


async def test_admin_force_stop_start(harness):
    harness.login()
    agent_id = _deploy_one(harness)
    await _promote(harness)
    c = harness.client
    assert c.post(f"/api/admin/agents/{agent_id}/stop").json()["status"] == "stopped"
    assert c.post(f"/api/admin/agents/{agent_id}/start").json()["status"] == "deployed"
    assert c.post(f"/api/admin/agents/{agent_id}/bogus").status_code == 400
