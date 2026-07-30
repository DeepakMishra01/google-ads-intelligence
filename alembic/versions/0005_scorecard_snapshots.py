"""Scorecard snapshots — persist weekly objective-vs-achieved reports.

Revision ID: 0005_scorecard_snapshots
Revises: 0004_dedupe_snapshots
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_scorecard_snapshots"
down_revision = "0004_dedupe_snapshots"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "scorecard_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("campus", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("generation_id", sa.Integer(), nullable=True),
        sa.Column("achieved_leads", sa.Numeric(16, 2), nullable=True),
        sa.Column("achieved_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("achieved_clicks", sa.Integer(), nullable=True),
        sa.Column("implementation_pct", sa.Integer(), nullable=True),
        sa.Column("expected_leads", sa.Numeric(16, 2), nullable=True),
        sa.Column("target_leads", sa.Integer(), nullable=True),
        sa.Column("payload", _JSON, nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["ad_copy_generations.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_scorecard_snapshots_campus", "scorecard_snapshots", ["campus"])
    op.create_index("ix_scorecard_snapshots_account_id", "scorecard_snapshots", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_scorecard_snapshots_account_id", table_name="scorecard_snapshots")
    op.drop_index("ix_scorecard_snapshots_campus", table_name="scorecard_snapshots")
    op.drop_table("scorecard_snapshots")
