"""Schemas for the sync engine's API surface."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

SyncTypeLiteral = Literal["hourly", "daily", "manual", "backfill"]

# The entities a manual sync can target. "all" runs the full pipeline.
SyncEntity = Literal[
    "all",
    "accounts",
    "campaigns",
    "ad_groups",
    "keywords",
    "ads",
    "search_terms",
    "budgets",
    "recommendations",
]


class SyncTriggerRequest(BaseModel):
    """Body for POST /sync - trigger an on-demand sync."""

    customer_ids: list[str] | None = Field(
        default=None,
        description="Google customer ids to sync. Omit to sync all syncable accounts.",
    )
    entity: SyncEntity = "all"
    lookback_days: int | None = Field(
        default=None, ge=1, le=365, description="Override the metric lookback window."
    )
    sync_type: SyncTypeLiteral = "manual"


class BackfillRequest(BaseModel):
    """Body for POST /sync/backfill - historical backfill over a date range."""

    customer_ids: list[str] | None = None
    start_date: str = Field(description="Inclusive start date, YYYY-MM-DD.")
    end_date: str = Field(description="Inclusive end date, YYYY-MM-DD.")
    entity: SyncEntity = "all"


class SyncLogRead(ORMModel):
    id: int
    sync_type: str
    entity: str
    customer_id: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    rows_inserted: int
    rows_updated: int
    rows_failed: int
    attempt: int
    error_message: str | None


class SyncRunResult(BaseModel):
    """Summary returned after a sync is executed."""

    status: str
    entity: str
    customer_ids: list[str]
    rows_inserted: int
    rows_updated: int
    rows_failed: int
    duration_ms: int
    log_ids: list[int]
    errors: list[str] = []


class SyncStatusResponse(BaseModel):
    scheduler_enabled: bool
    last_run: SyncLogRead | None
    recent_runs: list[SyncLogRead]
