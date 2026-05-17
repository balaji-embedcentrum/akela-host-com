"""Epic 11.2: maintenance sweeps — recycle lapsed rentals, renewal reminders,
orphan consistency check."""

from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import urlparse

import anyio

from backend.db.models import Agent
from backend.providers.factory import build_provider
from backend.services import sweeps


def _deploy(h) -> str:
    h.login()
    out = h.client.post("/api/agents/checkout", json={"display_name": "raj"}).json()
    pay = urlparse(out["checkout_url"])
    h.client.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    return out["agent_id"]


async def test_recycle_due_reclaims_lapsed_agent(harness):
    agent_id = _deploy(harness)
    fleet = build_provider("fleet", harness.settings)
    email = build_provider("email", harness.settings)

    # Simulate "cancelled, period ended yesterday".
    async with harness.db.sessionmaker() as s:
        a = await s.get(Agent, agent_id)
        a.status = "canceling"
        a.billing_period_end = date.today() - timedelta(days=1)
        await s.commit()

    async with harness.db.sessionmaker() as s:
        recycled = await sweeps.recycle_due(
            s, fleet=fleet, provisioner=harness.provisioner, email=email
        )
        await s.commit()

    assert recycled == [agent_id]
    assert (await fleet.get_available_slot()) is not None
    stats = harness.client.get("/api/fleet/stats").json()
    assert stats["available"] == 5
    raw = await anyio.Path(harness.settings.email_sink_path).read_text()
    tpls = [json.loads(x)["template"] for x in raw.splitlines()]
    assert "agent_recycled" in tpls


async def test_renewal_reminders(harness):
    agent_id = _deploy(harness)
    email = build_provider("email", harness.settings)
    async with harness.db.sessionmaker() as s:
        a = await s.get(Agent, agent_id)
        a.renewal_date = date.today() + timedelta(days=3)
        await s.commit()
    async with harness.db.sessionmaker() as s:
        reminded = await sweeps.renewal_reminders(s, email=email)
    assert reminded == [agent_id]


async def test_find_orphans_flags_stranded_slot(harness):
    agent_id = _deploy(harness)
    fleet = build_provider("fleet", harness.settings)

    async with harness.db.sessionmaker() as s:
        clean = await sweeps.find_orphans(s, fleet=fleet)
    assert clean == {"stranded_slots": [], "dangling_agents": []}

    # Agent goes dead but its slot is still assigned in the registry.
    async with harness.db.sessionmaker() as s:
        a = await s.get(Agent, agent_id)
        a.status = "recycled"
        await s.commit()
    async with harness.db.sessionmaker() as s:
        orphans = await sweeps.find_orphans(s, fleet=fleet)
    assert len(orphans["stranded_slots"]) == 1
