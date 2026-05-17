"""Epic 14 AC: sampled health → correct uptime % over the trailing window (D17)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from backend.db.models import Agent, AgentHealthSample, User
from backend.services.uptime import uptime_pct


async def test_uptime_pct_window_and_rounding(db):
    async with db.sessionmaker() as s:
        u = User(provider="mock", ext_id="u", email="u@x.com", username="u")
        s.add(u)
        await s.flush()
        a = Agent(user_id=u.id, display_name="a", status="deployed")
        b = Agent(user_id=u.id, display_name="b", status="deployed")
        s.add_all([a, b])
        await s.flush()
        now = datetime.now(UTC)
        s.add_all(
            [
                AgentHealthSample(agent_id=a.id, healthy=True, ts=now),
                AgentHealthSample(agent_id=a.id, healthy=True, ts=now),
                AgentHealthSample(agent_id=a.id, healthy=False, ts=now),
                # outside the 30d window — must be ignored
                AgentHealthSample(agent_id=a.id, healthy=True, ts=now - timedelta(days=40)),
            ]
        )
        await s.commit()
        result = await uptime_pct(s, [a.id, b.id])

    assert result[a.id] == 66.67  # 2 of 3 in-window
    assert result[b.id] is None  # no samples


async def test_sweep_samples_and_surfaces_uptime(harness):
    harness.login()
    c = harness.client
    out = c.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    c.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)

    # Promote to admin to trigger the sweep.
    me = c.get("/api/auth/me").json()
    async with harness.db.sessionmaker() as s:
        user = await s.get(User, me["id"])
        user.is_admin = True
        await s.commit()

    r = c.post("/api/admin/sweeps/run").json()
    assert r["sampled"] == 1  # one assigned slot probed

    detail = c.get(f"/api/agents/{out['agent_id']}").json()
    assert detail["uptime_pct"] == 100.0  # FakeProvisioner reports running

    c.post("/api/admin/sweeps/run")  # a second healthy sample
    assert c.get(f"/api/agents/{out['agent_id']}").json()["uptime_pct"] == 100.0
