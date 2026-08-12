"""Track who submitted a plan for approval, so we can email them the decision.

Revision ID: 0011_submitter
Revises: 0010_generation_owner
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_submitter"
down_revision = "0010_generation_owner"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "submitter_user_id"):
        op.add_column(
            "ad_copy_generations",
            sa.Column("submitter_user_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_ad_copy_generations_submitter_user_id",
            "ad_copy_generations",
            ["submitter_user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_col(insp, "ad_copy_generations", "submitter_user_id"):
        op.drop_index(
            "ix_ad_copy_generations_submitter_user_id",
            table_name="ad_copy_generations",
        )
        op.drop_column("ad_copy_generations", "submitter_user_id")
