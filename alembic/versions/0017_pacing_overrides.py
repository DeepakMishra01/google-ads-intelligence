"""Ad-manager overrides of the month-wise budget pacing (edited before approval).

Revision ID: 0017_pacing_overrides
Revises: 0016_result_payload
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_pacing_overrides"
down_revision = "0016_result_payload"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "pacing_overrides"):
        json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
        op.add_column(
            "ad_copy_generations",
            sa.Column("pacing_overrides", json_type, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_col(insp, "ad_copy_generations", "pacing_overrides"):
        op.drop_column("ad_copy_generations", "pacing_overrides")
