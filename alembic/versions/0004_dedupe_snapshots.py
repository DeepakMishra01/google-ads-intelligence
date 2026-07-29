"""Deduplicate snapshot tables (one row per entity + day).

The sync appended a fresh snapshot row every run, so overlapping sync windows
stacked duplicate (entity, snapshot_date) rows. Summing those rows inflated every
period metric (clicks, cost, conversions). This one-time migration keeps the
latest row per natural key and deletes the rest. Idempotent going forward is
handled in code (BaseRepository.replace_window).

Downgrade is a no-op — deleted duplicates carried no unique information.

Revision ID: 0004_dedupe_snapshots
Revises: 0003_ai_ad_copy
"""

from __future__ import annotations

from alembic import op

revision = "0004_dedupe_snapshots"
down_revision = "0003_ai_ad_copy"
branch_labels = None
depends_on = None

# table -> the columns that (with snapshot_date) identify one real daily row.
_SNAPSHOT_KEYS: dict[str, list[str]] = {
    "campaign_snapshots": ["campaign_id"],
    "campaign_device_snapshots": ["campaign_id", "device"],
    "campaign_geo_snapshots": ["campaign_id", "country_criterion_id"],
    "ad_group_snapshots": ["ad_group_id"],
    "keyword_snapshots": ["keyword_id"],
    "ad_snapshots": ["ad_id"],
    "search_term_snapshots": ["search_term_id", "campaign_id", "ad_group_id"],
    "budget_snapshots": ["budget_id"],
}


def upgrade() -> None:
    for table, keys in _SNAPSHOT_KEYS.items():
        partition = ", ".join([*keys, "snapshot_date"])
        op.execute(
            f"""
            DELETE FROM {table}
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY {partition}
                        ORDER BY sync_time DESC, id DESC
                    ) AS rn
                    FROM {table}
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        )


def downgrade() -> None:
    # Deleted rows were exact duplicates; nothing to restore.
    pass
