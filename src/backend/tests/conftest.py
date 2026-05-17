"""Shared test fixtures. All defaults run in mock mode with zero external accounts."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.db.session import Database


@pytest.fixture
def make_settings(tmp_path) -> Callable[..., Settings]:
    """Factory for isolated Settings (tmp sink/state, all modes mock by default).

    Pass `_env_file=None` so a developer's real .env never leaks into tests.
    """

    def _make(**overrides) -> Settings:
        base: dict = {
            "_env_file": None,
            "email_sink_path": str(tmp_path / "email-sink.jsonl"),
            "slots_host_root": str(tmp_path / "slots"),
            "jwt_secret": "test-secret-at-least-32-bytes-long-xx",
        }
        base.update(overrides)
        return Settings(**base)

    return _make


@pytest.fixture
def settings(make_settings) -> Settings:
    return make_settings()


@pytest_asyncio.fixture
async def db(tmp_path) -> AsyncIterator[Database]:
    """File-backed SQLite Database with both metadatas created (fleet schema
    translated to main). Hermetic — no Postgres/Docker needed."""
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.create_all()
    try:
        yield database
    finally:
        await database.dispose()


@dataclass
class Harness:
    client: TestClient
    settings: Settings
    db: Database
    provisioner: object = None

    def login(self) -> None:
        """Run the offline mock OAuth dance so subsequent requests are authed."""
        r = self.client.get("/api/auth/login", params={"provider": "mock"}, follow_redirects=False)
        from urllib.parse import urlparse

        cb = urlparse(r.headers["location"])
        self.client.get(f"/api/auth/callback?{cb.query}", follow_redirects=False)


class FakeProvisioner:
    """In-memory AgentProvisioner for API/e2e tests — no Docker. The real Docker
    path is covered by Epic 6's test_provisioner."""

    def __init__(self, settings: Settings) -> None:
        self.deployed: dict[str, str] = {}  # slot_name -> state

    async def deploy(self, slot, *, user_env, agent_api_key, display_name):
        from backend.providers.base import DeployResult

        self.deployed[slot.slot_name] = "running"
        return DeployResult(
            container_id=f"fake-{slot.slot_name}", a2a_url=slot.a2a_url, ws_url=slot.ws_url
        )

    async def stop(self, slot) -> None:
        self.deployed[slot.slot_name] = "stopped"

    async def start(self, slot) -> None:
        self.deployed[slot.slot_name] = "running"

    async def recycle(self, slot) -> None:
        self.deployed.pop(slot.slot_name, None)

    async def status(self, slot):
        from backend.providers.base import SlotRuntimeStatus

        state = self.deployed.get(slot.slot_name)
        return SlotRuntimeStatus(running=state == "running", health=state or "absent")


@pytest_asyncio.fixture
async def harness(tmp_path, make_settings) -> AsyncIterator[Harness]:
    """Wired app over sqlite + all-mock providers (provisioner faked, no Docker),
    with a seeded fleet pool. The whole HTTP surface is exercisable offline."""
    from backend.db.session import get_database_for
    from backend.dependencies import get_database, get_provisioner, get_settings_dep
    from backend.main import create_app
    from backend.scripts.seed import seed

    url = f"sqlite+aiosqlite:///{tmp_path / 'app.db'}"
    settings = make_settings(database_url=url, fleet_seed_slots=5)
    database = get_database_for(url)
    await database.create_all()
    await seed(database, settings)

    fake = FakeProvisioner(settings)
    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_provisioner] = lambda: fake

    with TestClient(app) as client:
        yield Harness(client=client, settings=settings, db=database, provisioner=fake)


@pytest_asyncio.fixture
async def seeded_pool(tmp_path, make_settings) -> Settings:
    """Settings whose DB has a seeded fleet pool (1 VPS + N available slots)."""
    from backend.db.session import get_database_for
    from backend.scripts.seed import seed

    url = f"sqlite+aiosqlite:///{tmp_path / 'pool.db'}"
    settings = make_settings(database_url=url)
    database = get_database_for(url)
    await database.create_all()
    await seed(database, settings)
    return settings


def has_env(*names: str) -> bool:
    return all(os.environ.get(n) for n in names)
