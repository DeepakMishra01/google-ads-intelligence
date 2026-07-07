"""Initial baseline schema.

This baseline migration builds every table directly from the application's
SQLAlchemy metadata, so the schema is guaranteed to match the ORM models with no
hand-transcription drift. All *subsequent* migrations should be produced with
``alembic revision --autogenerate`` and will diff correctly against this
baseline (Alembic autogenerate reflects the live DB, not this file).

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.models import Base

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
