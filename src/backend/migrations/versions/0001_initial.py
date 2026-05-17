"""schema baseline — web-app DB + fleet registry (metadata-managed; D19)

Revision ID: 0001
Revises:
Create Date: 2026-05-17

Pre-launch the schema is owned by the ORM metadata: this single migration is
`create_all`/`drop_all` of the *current* models (Phase 1 + 2), guaranteeing zero
drift. At launch this becomes a frozen baseline and subsequent changes get real
incremental migrations (see docs/DECISIONS.md D19). The `fleet` schema is ensured
by migrations/env.py before this runs.
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
