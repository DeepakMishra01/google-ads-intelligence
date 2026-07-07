"""Sync run bookkeeping: one row per (run, entity, account) execution."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin

# JSONB on Postgres (indexable, efficient); plain JSON on SQLite for tests.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class SyncType(enum.StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    MANUAL = "manual"
    BACKFILL = "backfill"


class SyncStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncLog(IntPKMixin, Base):
    """Execution record for a sync task. Drives observability & partial recovery."""

    __tablename__ = "sync_logs"

    sync_type: Mapped[str] = mapped_column(String(16), index=True)
    entity: Mapped[str] = mapped_column(String(48), index=True)  # campaigns, keywords...
    # Google customer id being synced (string; null for account-discovery runs).
    customer_id: Mapped[str | None] = mapped_column(String(20), index=True)

    status: Mapped[str] = mapped_column(String(16), default=SyncStatus.RUNNING.value, index=True)
    started_at: Mapped[datetime] = mapped_column(index=True)
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)

    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    # Arbitrary structured context (date window, page counts, etc.).
    details: Mapped[dict | None] = mapped_column(JSONType)
