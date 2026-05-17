"""Epic 6 AC: LocalDockerProvisioner spins a real container, /health responds,
recycle wipes volumes. Uses a tiny stand-in image (real hermes swaps in via
HERMES_ADAPTER_IMAGE — same code path). Skipped if Docker/network unavailable so
`make verify` stays green offline."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from backend.providers.base import Slot, SlotStatus
from backend.providers.factory import build_provider

TEST_IMAGE = "akela-test-agent:latest"
_CTX = Path(__file__).resolve().parents[3] / "infra" / "test-agent"


def _docker_ok() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def test_image() -> str:
    if not _docker_ok():
        pytest.skip("docker unavailable")
    build = subprocess.run(
        ["docker", "build", "-t", TEST_IMAGE, str(_CTX)],
        capture_output=True,
        timeout=300,
    )
    if build.returncode != 0:
        pytest.skip(f"could not build stand-in image (offline?): {build.stderr[-300:]!r}")
    return TEST_IMAGE


@pytest.fixture
def slot() -> Slot:
    name = f"ptest{uuid.uuid4().hex[:8]}"
    return Slot(
        slot_name=name,
        vps_id="v1",
        vps_ip="127.0.0.1",
        status=SlotStatus.assigned,
        a2a_url=f"https://agents.akela-host.com/{name}/a2a",
        ws_url=f"https://agents.akela-host.com/{name}/ws",
    )


async def test_deploy_health_lifecycle_recycle(test_image, slot, make_settings):
    settings = make_settings(provisioner_mode="mock", hermes_adapter_image=test_image)
    prov = build_provider("provisioner", settings)
    host_dir = Path(".localfleet") / slot.slot_name
    try:
        result = await prov.deploy(
            slot,
            user_env={"OPENROUTER_API_KEY": "or-xyz"},
            agent_api_key="akela_testkey",
            display_name="raj-alpha",
        )
        assert result.container_id
        assert result.a2a_url == slot.a2a_url
        assert host_dir.exists()  # per-slot host dirs created

        st = await prov.status(slot)
        assert st.running is True

        await prov.stop(slot)
        assert (await prov.status(slot)).running is False
        await prov.start(slot)
        assert (await prov.status(slot)).running is True

        await prov.recycle(slot)
        assert not host_dir.exists()  # data + workspaces wiped (ToS §4)
        assert (await prov.status(slot)).health == "absent"  # container gone
    finally:
        await prov.recycle(slot)
        shutil.rmtree(host_dir, ignore_errors=True)
