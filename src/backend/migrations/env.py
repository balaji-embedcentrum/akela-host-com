"""Async Alembic env. URL comes from backend.config (single source of truth).
Targets both metadatas; ensures the `fleet` schema exists on Postgres."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.config import get_settings
from backend.db import FLEET_SCHEMA, fleet_models, models  # noqa: F401  (register tables)
from backend.db.base import Base, FleetBase

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = [Base.metadata, FleetBase.metadata]


def _run(connection) -> None:
    if connection.dialect.name != "sqlite":
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{FLEET_SCHEMA}"'))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy."
    )
    # engine.begin() commits on clean exit — guarantees the migration + the
    # alembic_version stamp persist (engine.connect() left them uncommitted under
    # the asyncpg greenlet bridge).
    async with engine.begin() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_schemas=True,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_async())
