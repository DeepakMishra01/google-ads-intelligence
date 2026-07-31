"""Approval token — backs the one-click Approve/Reject email links.

Revision ID: 0007_approval_token
Revises: 0006_approval_workflow
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_approval_token"
down_revision = "0006_approval_workflow"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "approval_token"):
        op.add_column(
            "ad_copy_generations",
            sa.Column("approval_token", sa.String(length=64), nullable=True),
        )
    existing_idx = {i["name"] for i in insp.get_indexes("ad_copy_generations")}
    if "ix_ad_copy_generations_approval_token" not in existing_idx:
        op.create_index(
            "ix_ad_copy_generations_approval_token",
            "ad_copy_generations",
            ["approval_token"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_copy_generations_approval_token", table_name="ad_copy_generations"
    )
    op.drop_column("ad_copy_generations", "approval_token")
