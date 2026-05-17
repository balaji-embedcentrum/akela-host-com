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

    def login(self) -> None:
        """Run the offline mock OAuth dance so subsequent requests are authed."""
        r = self.client.get("/api/auth/login", params={"provider": "mock"}, follow_redirects=False)
        from urllib.parse import urlparse

        cb = urlparse(r.headers["location"])
        self.client.get(f"/api/auth/callback?{cb.query}", follow_redirects=False)


@pytest_asyncio.fixture
async def harness(tmp_path, make_settings) -> AsyncIterator[Harness]:
    """Wired app over sqlite + all-mock providers. Overrides settings/db DI so the
    whole HTTP surface is exercisable offline with zero external accounts."""
    from backend.dependencies import get_database, get_settings_dep
    from backend.main import create_app

    url = f"sqlite+aiosqlite:///{tmp_path / 'app.db'}"
    settings = make_settings(database_url=url)
    database = Database(url)
    await database.create_all()

    app = create_app()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database

    with TestClient(app) as client:
        yield Harness(client=client, settings=settings, db=database)
    await database.dispose()


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
