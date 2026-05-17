"""Epic 3 AC: full login → session → logout works offline via mock."""

from __future__ import annotations

from urllib.parse import urlparse


def test_login_callback_me_logout(harness):
    c = harness.client

    # 1. /login → 302 to the (mock) IdP, which bounces back to our callback.
    r = c.get(
        "/api/auth/login",
        params={"provider": "mock", "redirect": "/dashboard"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    cb = urlparse(r.headers["location"])
    assert cb.path == "/api/auth/callback"

    # 2. callback → sets session cookie, 302 to the SPA.
    r = c.get(f"/api/auth/callback?{cb.query}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/dashboard")
    assert "akela_session" in r.cookies or "akela_session" in c.cookies

    # 3. authenticated /me works.
    r = c.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock"
    assert "@" in body["email"]
    assert body["is_admin"] is False

    # 4. logout clears the session.
    assert c.post("/api/auth/logout").status_code == 200
    c.cookies.clear()
    assert c.get("/api/auth/me").status_code == 401


def test_me_requires_auth(harness):
    assert harness.client.get("/api/auth/me").status_code == 401


def test_bad_state_rejected(harness):
    r = harness.client.get(
        "/api/auth/callback?code=mock-auth-code&state=forged", follow_redirects=False
    )
    assert r.status_code == 400
