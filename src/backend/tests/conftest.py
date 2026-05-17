"""Shared test fixtures. All defaults run in mock mode with zero external accounts."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio

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
            "jwt_secret": "test-secret",
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


def has_env(*names: str) -> bool:
    return all(os.environ.get(n) for n in names)
