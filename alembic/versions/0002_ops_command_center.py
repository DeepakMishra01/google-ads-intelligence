"""Phase 2: alerts + audit_logs tables and composite performance indexes.

New tables are created from the ORM metadata (idempotent). Composite indexes on
the Phase 1 snapshot tables accelerate the Command Center's date-range + account
scans and are created with ``IF NOT EXISTS`` so the migration is re-runnable.

Revision ID: 0002_ops
Revises: 0001_initial
Create Date: 2026-07-07 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.models import Base

revision: str = "0002_ops"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table, columns) for the composite performance indexes.
_PERF_INDEXES = [
    ("ix_campaign_snapshots_account_date", "campaign_snapshots", "account_id, snapshot_date"),
    ("ix_campaign_snapshots_campaign_date", "campaign_snapshots", "campaign_id, snapshot_date"),
    ("ix_keyword_snapshots_account_date", "keyword_snapshots", "account_id, snapshot_date"),
    ("ix_keyword_snapshots_keyword_date", "keyword_snapshots", "keyword_id, snapshot_date"),
    ("ix_ad_snapshots_account_date", "ad_snapshots", "account_id, snapshot_date"),
    ("ix_search_term_snapshots_account_date", "search_term_snapshots", "account_id, snapshot_date"),
    ("ix_budget_snapshots_budget_date", "budget_snapshots", "budget_id, snapshot_date"),
]


def upgrade() -> None:
    # Create only the new Phase 2 tables (create_all skips existing tables).
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[Base.metadata.tables["alerts"], Base.metadata.tables["audit_logs"]],
    )
    for name, table, cols in _PERF_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def downgrade() -> None:
    for name, _table, _cols in _PERF_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.drop_table("audit_logs")
    op.drop_table("alerts")
