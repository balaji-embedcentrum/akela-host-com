"""initial schema — web-app DB + fleet registry

Revision ID: 0001
Revises:
Create Date: 2026-05-17

Creates every table from the ORM metadata (parity with models, zero drift). The
`fleet` schema is ensured by migrations/env.py before this runs.
"""

from __future__ import annotations

from alembic import op

from backend.db import fleet_models, models  # noqa: F401  (register tables)
from backend.db.base import Base, FleetBase

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    FleetBase.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    FleetBase.metadata.drop_all(bind)
    Base.metadata.drop_all(bind)
