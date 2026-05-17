"""Epic 11.2: auth + checkout are rate limited (fixed window, per-app state)."""

from __future__ import annotations


def test_login_is_rate_limited(harness):
    c = harness.client
    # Limit is 50/min for "login"; the 51st in the same window is 429.
    codes = [
        c.get("/api/auth/login", params={"provider": "mock"}, follow_redirects=False).status_code
        for _ in range(51)
    ]
    assert codes[:50] == [302] * 50
    assert codes[50] == 429


def test_checkout_is_rate_limited(harness):
    harness.login()
    c = harness.client
    codes = [
        c.post("/api/agents/checkout", json={"display_name": f"a{i}"}).status_code
        for i in range(31)
    ]
    assert codes.count(200) == 30
    assert codes[-1] == 429
