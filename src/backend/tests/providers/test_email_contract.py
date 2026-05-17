"""EmailProvider contract — runs against every available impl. This is the reference
pattern every provider's contract suite follows: parametrize over `mock` (always) and
`real` (skipped unless its credentials are present). See docs/ARCHITECTURE.md §3.6."""

from __future__ import annotations

import json

import anyio
import pytest

from backend.providers.base import EmailProvider
from backend.providers.factory import build_provider

from ..conftest import has_env

EMAIL_MODES = [
    "mock",
    pytest.param(
        "real",
        marks=pytest.mark.skipif(
            not has_env("RESEND_API_KEY"), reason="no RESEND_API_KEY — real email skipped"
        ),
    ),
]


@pytest.fixture(params=EMAIL_MODES)
def email_provider(request, make_settings) -> tuple[EmailProvider, str]:
    mode = request.param
    settings = make_settings(email_mode=mode)
    return build_provider("email", settings), settings.email_sink_path


async def test_send_known_template_succeeds(email_provider):
    provider, _ = email_provider
    await provider.send(
        to="user@example.com",
        template="agent_deployed",
        context={"agent": "raj-alpha", "a2a_url": "https://x/a2a"},
    )


async def test_unknown_template_rejected(email_provider):
    provider, _ = email_provider
    with pytest.raises(ValueError):
        await provider.send(to="user@example.com", template="not_a_template", context={})


async def test_mock_writes_to_sink(email_provider):
    provider, sink_path = email_provider
    if provider.__class__.__name__ != "ConsoleEmail":
        pytest.skip("sink assertion is mock-specific")
    await provider.send(to="a@b.com", template="welcome", context={"name": "Raj"})
    raw = await anyio.Path(sink_path).read_text()
    lines = [json.loads(x) for x in raw.splitlines()]
    assert lines[-1]["to"] == "a@b.com"
    assert lines[-1]["template"] == "welcome"
    assert lines[-1]["subject"]
