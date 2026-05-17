"""Epic 15 AC: referred signup + first deploy grants exactly one month credit;
unknown/self codes grant nothing (D18)."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import func, select

from backend.db.models import User


def _login_with_ref(h, ref: str) -> None:
    r = h.client.get(
        "/api/auth/login",
        params={"provider": "mock", "ref": ref},
        follow_redirects=False,
    )
    cb = urlparse(r.headers["location"])
    h.client.get(f"/api/auth/callback?{cb.query}", follow_redirects=False)


def _deploy(h, name: str) -> str:
    out = h.client.post("/api/agents/checkout", json={"display_name": name}).json()
    pay = urlparse(out["checkout_url"])
    h.client.get(f"/api/billing/mock-pay?{pay.query}", follow_redirects=False)
    return out["agent_id"]


async def test_referral_grants_one_credit_once(harness):
    # A pre-existing referrer with a known code.
    async with harness.db.sessionmaker() as s:
        referrer = User(
            provider="mock",
            ext_id="referrer",
            email="ref@x.com",
            username="ref",
            referral_code="REFERRER01",
        )
        s.add(referrer)
        await s.commit()
        referrer_id = referrer.id

    _login_with_ref(harness, "REFERRER01")  # new (referred) mock user
    me = harness.client.get("/api/auth/me").json()
    assert me["id"] != referrer_id

    _deploy(harness, "first")
    async with harness.db.sessionmaker() as s:
        r1 = await s.get(User, referrer_id)
        assert r1.credit_cents == 400  # one month, granted on first deploy

    _deploy(harness, "second")  # second agent — no extra credit
    async with harness.db.sessionmaker() as s:
        r2 = await s.get(User, referrer_id)
        assert r2.credit_cents == 400

    # Referrer's stats reflect exactly one referred user.
    async with harness.db.sessionmaker() as s:
        n = (
            await s.execute(
                select(func.count())
                .select_from(User)
                .where(User.referred_by_user_id == referrer_id)
            )
        ).scalar_one()
    assert n == 1


def test_unknown_ref_code_is_safe(harness):
    _login_with_ref(harness, "DOESNOTEXIST")
    r = harness.client.get("/api/referrals/me").json()
    assert r["code"] and r["referred_count"] == 0 and r["earned_cents"] == 0


async def test_self_referral_grants_nothing(harness):
    harness.login()
    me = harness.client.get("/api/auth/me").json()
    async with harness.db.sessionmaker() as s:
        u = await s.get(User, me["id"])
        u.referred_by_user_id = u.id  # contrived self-referral
        await s.commit()
    _deploy(harness, "solo")
    async with harness.db.sessionmaker() as s:
        u = await s.get(User, me["id"])
        assert u.credit_cents == 0
