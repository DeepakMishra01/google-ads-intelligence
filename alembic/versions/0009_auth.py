"""Google sign-in + per-account access control.

Adds Google identity columns to ``users`` and the ``user_accounts`` grant table
that scopes a manager to specific Google Ads accounts.

Revision ID: 0009_auth
Revises: 0008_ad_manager
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_auth"
down_revision = "0008_ad_manager"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def _has_table(insp, table: str) -> bool:
    return table in insp.get_table_names()


def _has_index(insp, table: str, name: str) -> bool:
    return name in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _has_col(insp, "users", "google_sub"):
        op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    if not _has_index(insp, "users", "ix_users_google_sub"):
        op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    if not _has_col(insp, "users", "picture"):
        op.add_column("users", sa.Column("picture", sa.String(length=1024), nullable=True))
    if not _has_col(insp, "users", "last_login_at"):
        op.add_column(
            "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
        )

    if not _has_table(insp, "user_accounts"):
        op.create_table(
            "user_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "account_id",
                sa.Integer(),
                sa.ForeignKey("accounts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("user_id", "account_id", name="user_accounts_user_account"),
        )
        op.create_index("ix_user_accounts_user_id", "user_accounts", ["user_id"])
        op.create_index("ix_user_accounts_account_id", "user_accounts", ["account_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_table(insp, "user_accounts"):
        op.drop_table("user_accounts")
    for idx in ("ix_users_google_sub",):
        if _has_index(insp, "users", idx):
            op.drop_index(idx, table_name="users")
    for col in ("last_login_at", "picture", "google_sub"):
        if _has_col(insp, "users", col):
            op.drop_column("users", col)
