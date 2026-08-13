"""Admin-allocated weekly budgets per account.

Revision ID: 0013_weekly_budget
Revises: 0012_keyword_edits
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_weekly_budget"
down_revision = "0012_keyword_edits"
branch_labels = None
depends_on = None


def _has_table(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_table(insp, "account_weekly_budgets"):
        op.create_table(
            "account_weekly_budgets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "account_id", sa.Integer(),
                sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("set_by", sa.String(length=160), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("account_id", "week_start", name="account_weekly_budget_uq"),
        )
        op.create_index("ix_account_weekly_budgets_account_id",
                        "account_weekly_budgets", ["account_id"])
        op.create_index("ix_account_weekly_budgets_week_start",
                        "account_weekly_budgets", ["week_start"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_table(insp, "account_weekly_budgets"):
        op.drop_table("account_weekly_budgets")
