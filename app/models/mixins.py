"""Reusable ORM mixins: primary keys, timestamps, snapshot & metric columns.

Design rules
------------
* Dimension tables (accounts, campaigns, ...) hold the *current* known state of
  an entity and are upserted by natural key. They carry `TimestampMixin`.
* Snapshot tables are **append-only** time-series. They carry `SnapshotMixin`
  and (where they hold performance data) `MetricsMixin`. Historical rows are
  never updated or deleted.

Every snapshot row records:
  * ``snapshot_date`` - the reporting date the data belongs to (the "timestamp"
    dimension used for time-series queries).
  * ``sync_time``     - when the sync engine wrote the row.
  * ``account_id``    - owning Google Ads account (FK).
  * ``sync_log_id``   - the sync run that produced it (FK, for traceability).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column


class IntPKMixin:
    """Surrogate integer primary key.

    Uses 32-bit ``Integer`` (max ~2.1B rows/table) which autoincrements
    identically on PostgreSQL and SQLite and keeps every internal FK type
    consistent. Google's own ids and monetary micros use ``BigInteger`` where
    they genuinely need 64 bits. Migrating a hot snapshot table to BigInteger
    later is a single ALTER.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class TimestampMixin:
    """Row-level audit timestamps for mutable dimension rows."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SnapshotMixin:
    """Common columns for every append-only snapshot table."""

    snapshot_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    sync_time: Mapped[datetime] = mapped_column(
        server_default=func.now(), index=True, nullable=False
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sync_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("sync_logs.id", ondelete="SET NULL"), nullable=True
    )


class MetricsMixin:
    """Standard Google Ads performance metrics.

    Monetary values are stored in *micros* (1/1,000,000 of the account currency)
    exactly as returned by the API - integer, lossless. Ratios/conversions are
    stored as provided.
    """

    impressions: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    interactions: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    ctr: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    average_cpc_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    average_cpm_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[float] = mapped_column(Numeric(16, 4), default=0, nullable=False)
    conversions_value: Mapped[float] = mapped_column(Numeric(18, 4), default=0, nullable=False)
    all_conversions: Mapped[float] = mapped_column(Numeric(16, 4), default=0, nullable=False)
    video_views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
