"""Declarative bases. `Base` = web-app DB (no schema). `FleetBase` = fleet registry
(schema-qualified). On SQLite the `fleet` schema is collapsed to main via
`schema_translate_map` (see db/session.py) so tests need no Postgres."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from backend.db import FLEET_SCHEMA

# Stable constraint names → clean Alembic diffs / portable DDL.
_NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)


class FleetBase(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING, schema=FLEET_SCHEMA)
