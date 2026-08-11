"""Signed-in owner on a generation — bridges Accountability ownership to access.

Adds ``ad_copy_generations.owner_user_id`` (FK users.id). An AM assigned as owner
of a campaign/campus in the Accountability tab gains access to that generation's
account.

Revision ID: 0010_generation_owner
Revises: 0009_auth
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_generation_owner"
down_revision = "0009_auth"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, name: str) -> bool:
    return name in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "owner_user_id"):
        op.add_column(
            "ad_copy_generations",
            sa.Column(
                "owner_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if not _has_index(insp, "ad_copy_generations", "ix_ad_copy_generations_owner_user_id"):
        op.create_index(
            "ix_ad_copy_generations_owner_user_id",
            "ad_copy_generations",
            ["owner_user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_index(insp, "ad_copy_generations", "ix_ad_copy_generations_owner_user_id"):
        op.drop_index(
            "ix_ad_copy_generations_owner_user_id", table_name="ad_copy_generations"
        )
    if _has_col(insp, "ad_copy_generations", "owner_user_id"):
        op.drop_column("ad_copy_generations", "owner_user_id")
