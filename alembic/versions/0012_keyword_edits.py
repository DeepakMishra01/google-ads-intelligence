"""User keyword edits (added / removed) on a generation, for the approval plan.

Revision ID: 0012_keyword_edits
Revises: 0011_submitter
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_keyword_edits"
down_revision = "0011_submitter"
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _has_col(insp, "ad_copy_generations", "keyword_edits"):
        # JSON on Postgres, generic JSON elsewhere (SQLite in tests).
        json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
        op.add_column(
            "ad_copy_generations",
            sa.Column("keyword_edits", json_type, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _has_col(insp, "ad_copy_generations", "keyword_edits"):
        op.drop_column("ad_copy_generations", "keyword_edits")
