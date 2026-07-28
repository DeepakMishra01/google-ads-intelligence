"""Phase 3: AI Ad Copy Generator — ad_copy_generations table.

Creates the generation-history table from ORM metadata (idempotent) plus a
composite index for listing a campus/account's recent generations. Mirrors the
0002 pattern.

Revision ID: 0003_ai_ad_copy
Revises: 0002_ops
Create Date: 2026-07-28 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0003_ai_ad_copy"
down_revision: str | None = "0002_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    (
        "ix_ad_copy_generations_account_created",
        "ad_copy_generations",
        "account_id, created_at",
    ),
    (
        "ix_ad_copy_generations_campus_created",
        "ad_copy_generations",
        "campus, created_at",
    ),
]


def upgrade() -> None:
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[Base.metadata.tables["ad_copy_generations"]],
    )
    for name, table, cols in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def downgrade() -> None:
    for name, _table, _cols in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.drop_table("ad_copy_generations")
