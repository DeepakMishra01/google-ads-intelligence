"""Store the full generate() result so saved plans can be re-opened in the UI.

Revision ID: 0016_result_payload
Revises: 0015_asset_edits
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016_result_payload"
down_revision = "0015_asset_edits"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "result_payload"):
        json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
        op.add_column(
            "ad_copy_generations",
            sa.Column("result_payload", json_type, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_col(insp, "ad_copy_generations", "result_payload"):
        op.drop_column("ad_copy_generations", "result_payload")
