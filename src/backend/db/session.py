"""Async engine/session. One engine serves both metadatas. On SQLite the `fleet`
schema is translated away (so unit/contract tests need no Postgres); on Postgres the
schema is created and used as-is (docs/ARCHITECTURE.md §6)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import Settings, get_settings

# Import models so their tables register on the metadatas before create_all.
from backend.db import FLEET_SCHEMA, fleet_models, models  # noqa: F401  (side-effect import)
from backend.db.base import Base, FleetBase


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _schema_map(url: str) -> dict[str, str | None]:
    # SQLite has no schemas → collapse `fleet` into main.
    return {FLEET_SCHEMA: None} if _is_sqlite(url) else {}


class Database:
    def __init__(self, url: str) -> None:
        self._url = url
        kwargs: dict = {"future": True}
        if _is_sqlite(url):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_async_engine(url, **kwargs).execution_options(
            schema_translate_map=_schema_map(url)
        )
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        """Create both schemas/metadatas. Used by tests and `make seed`'s ensure step."""
        async with self.engine.begin() as conn:
            if not _is_sqlite(self._url):
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{FLEET_SCHEMA}"'))
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(FleetBase.metadata.create_all)

    async def drop_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(FleetBase.metadata.drop_all)
            await conn.run_sync(Base.metadata.drop_all)

    async def dispose(self) -> None:
        await self.engine.dispose()


_db: Database | None = None


def get_db(settings: Settings | None = None) -> Database:
    """Process-wide Database singleton (built from settings on first use)."""
    global _db
    if _db is None:
        _db = Database((settings or get_settings()).database_url)
    return _db


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a transactional session per request."""
    db = get_db()
    async with db.sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
