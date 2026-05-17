"""Epic 2 AC: Alembic migrations apply and reverse cleanly. Postgres-only (the
`fleet` schema is real DDL there); skipped locally without a test Postgres, runs
in CI against the postgres service.

Sync test on purpose: alembic's env.py drives its own event loop (asyncio.run), so
it must not run inside pytest-asyncio's loop. Table inspection uses a separate
asyncio.run + the async engine (asyncpg) so no sync driver (psycopg2) is needed.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import get_settings

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="no TEST_DATABASE_URL — Postgres migration round-trip skipped"
)


async def _table_names(url: str, schema: str | None = None) -> list[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(lambda c: inspect(c).get_table_names(schema=schema))
    finally:
        await engine.dispose()


def test_migration_upgrade_then_downgrade(monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    get_settings.cache_clear()
    cfg = Config("alembic.ini")

    # Self-clean: a prior failed run may have left tables at head.
    try:
        command.downgrade(cfg, "base")
    except Exception:
        pass

    command.upgrade(cfg, "head")
    public = asyncio.run(_table_names(TEST_DB))
    fleet = asyncio.run(_table_names(TEST_DB, schema="fleet"))
    assert {"users", "agents", "subscriptions", "processed_events"} <= set(public)
    assert {"agent_slots", "vps_servers", "vps_ssh_keys"} <= set(fleet)

    command.downgrade(cfg, "base")
    public_after = asyncio.run(_table_names(TEST_DB))
    assert "users" not in public_after and "agents" not in public_after

    get_settings.cache_clear()
