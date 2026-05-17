"""Epic 6 (no Docker): the per-slot hermes contract is rendered correctly and the
user's env can never clobber the reserved contract keys (D6/D12)."""

from __future__ import annotations

from backend.providers.base import Slot, SlotStatus
from backend.providers.compose import build_env, render_compose

SLOT = Slot(
    slot_name="hermesagent1",
    vps_id="v1",
    vps_ip="127.0.0.1",
    status=SlotStatus.available,
    a2a_url="https://agents.akela-host.com/hermesagent1/a2a",
    ws_url="https://agents.akela-host.com/hermesagent1/ws",
)


def test_build_env_has_contract_and_user_layered(settings):
    env = build_env(
        SLOT,
        settings=settings,
        agent_api_key="akela_secret",
        display_name="raj-alpha",
        user_env={"OPENROUTER_API_KEY": "or-123", "GITHUB_TOKEN": "gh-1"},
    )
    assert env["API_SERVER_KEY"] == "akela_secret"  # == AKELA_API_KEY (D6)
    assert env["A2A_PORT"] == "9000" and env["HERMES_ADAPTER_PORT"] == "8766"
    assert env["A2A_PUBLIC_URL"] == SLOT.a2a_url
    assert env["OPENROUTER_API_KEY"] == "or-123"  # user secret passed verbatim (D7)
    assert env["GITHUB_TOKEN"] == "gh-1"


def test_user_env_cannot_override_reserved(settings):
    env = build_env(
        SLOT,
        settings=settings,
        agent_api_key="real-key",
        display_name="x",
        user_env={"API_SERVER_KEY": "attacker", "A2A_PORT": "1"},
    )
    assert env["API_SERVER_KEY"] == "real-key"  # not hijacked
    assert env["A2A_PORT"] == "9000"


def test_render_compose_matches_contract(settings):
    yml = render_compose(SLOT, settings=settings, display_name="raj", host_dir="/opt/x")
    assert settings.hermes_adapter_image in yml
    assert "container_name: slot-hermesagent1" in yml
    assert "env_file: [/opt/x/.env]" in yml  # secrets via root-only file, not DB
    assert "/opt/x/data:/opt/data" in yml
    assert ":8766/health" in yml
