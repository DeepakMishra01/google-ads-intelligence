"""Ad manager owner on a generation — enables per-manager performance rollups.

Revision ID: 0008_ad_manager
Revises: 0007_approval_token
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_ad_manager"
down_revision = "0007_approval_token"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "ad_manager"):
        op.add_column(
            "ad_copy_generations",
            sa.Column("ad_manager", sa.String(length=160), nullable=True),
        )
    existing_idx = {i["name"] for i in insp.get_indexes("ad_copy_generations")}
    if "ix_ad_copy_generations_ad_manager" not in existing_idx:
        op.create_index(
            "ix_ad_copy_generations_ad_manager",
            "ad_copy_generations",
            ["ad_manager"],
        )


def downgrade() -> None:
    op.drop_index("ix_ad_copy_generations_ad_manager", table_name="ad_copy_generations")
    op.drop_column("ad_copy_generations", "ad_manager")
