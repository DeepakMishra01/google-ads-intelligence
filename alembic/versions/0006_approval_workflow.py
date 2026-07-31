"""Approval workflow — status/overrides on generations + approval_events log.

Revision ID: 0006_approval_workflow
Revises: 0005_scorecard_snapshots
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0006_approval_workflow"
down_revision = "0005_scorecard_snapshots"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols = [
        ("approval_status", sa.String(length=16), {"server_default": "draft", "nullable": False}),
        ("submitted_at", sa.DateTime(), {"nullable": True}),
        ("reviewed_at", sa.DateTime(), {"nullable": True}),
        ("reviewer_name", sa.String(length=160), {"nullable": True}),
        ("review_note", sa.Text(), {"nullable": True}),
        ("overrides", _JSON, {"nullable": True}),
    ]
    for name, type_, kw in cols:
        if not _has_col(insp, "ad_copy_generations", name):
            op.add_column("ad_copy_generations", sa.Column(name, type_, **kw))
    if "ad_copy_generations" in insp.get_table_names():
        existing_idx = {i["name"] for i in insp.get_indexes("ad_copy_generations")}
        if "ix_ad_copy_generations_approval_status" not in existing_idx:
            op.create_index(
                "ix_ad_copy_generations_approval_status",
                "ad_copy_generations",
                ["approval_status"],
            )

    if not insp.has_table("approval_events"):
        op.create_table(
            "approval_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("generation_id", sa.Integer(), nullable=False),
            sa.Column("event", sa.String(length=24), nullable=False),
            sa.Column("actor", sa.String(length=160), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["generation_id"], ["ad_copy_generations.id"], ondelete="CASCADE"
            ),
        )
        op.create_index(
            "ix_approval_events_generation_id", "approval_events", ["generation_id"]
        )


def downgrade() -> None:
    op.drop_table("approval_events")
    op.drop_index(
        "ix_ad_copy_generations_approval_status", table_name="ad_copy_generations"
    )
    for name in ("overrides", "review_note", "reviewer_name", "reviewed_at",
                 "submitted_at", "approval_status"):
        op.drop_column("ad_copy_generations", name)
