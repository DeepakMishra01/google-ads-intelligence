"""Sync control endpoints: trigger, backfill, status, logs."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.config.settings import Settings, get_settings
from app.database.session import get_db
from app.repositories.sync_log import SyncLogRepository
from app.schemas.common import Message
from app.schemas.sync import (
    BackfillRequest,
    SyncLogRead,
    SyncRunResult,
    SyncStatusResponse,
    SyncTriggerRequest,
)
from app.tasks.sync_tasks import (
    run_backfill,
    run_backfill_safe,
    run_sync,
    run_sync_safe,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post(
    "",
    response_model=SyncRunResult | Message,
    summary="Trigger an on-demand sync",
    dependencies=[Depends(require_api_key)],
)
def trigger_sync(
    payload: SyncTriggerRequest,
    background: BackgroundTasks,
    run_in_background: bool = Query(
        True, description="Return immediately and run the sync in the background."
    ),
) -> SyncRunResult | Message:
    kwargs = {
        "customer_ids": payload.customer_ids,
        "entity": payload.entity,
        "lookback_days": payload.lookback_days,
        "sync_type": payload.sync_type,
    }
    if run_in_background:
        background.add_task(run_sync_safe, **kwargs)
        return Message(
            message="Sync accepted and running in the background. Poll GET /sync/status."
        )
    return run_sync(**kwargs)


@router.post(
    "/backfill",
    response_model=SyncRunResult | Message,
    summary="Backfill historical snapshots over a date range",
    dependencies=[Depends(require_api_key)],
)
def trigger_backfill(
    payload: BackfillRequest,
    background: BackgroundTasks,
    run_in_background: bool = Query(True),
) -> SyncRunResult | Message:
    try:
        start = date.fromisoformat(payload.start_date)
        end = date.fromisoformat(payload.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date: {exc}") from exc
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")

    kwargs = {
        "start_date": start,
        "end_date": end,
        "customer_ids": payload.customer_ids,
        "entity": payload.entity,
    }
    if run_in_background:
        background.add_task(run_backfill_safe, **kwargs)
        return Message(message="Backfill accepted and running in the background.")
    return run_backfill(**kwargs)


@router.get("/status", response_model=SyncStatusResponse, summary="Sync status & history")
def sync_status(
    limit: int = Query(20, ge=1, le=200),
    customer_id: str | None = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    repo = SyncLogRepository(db)
    recent = repo.recent(limit=limit, customer_id=customer_id)
    latest = repo.latest()
    return SyncStatusResponse(
        scheduler_enabled=settings.scheduler_enabled,
        last_run=SyncLogRead.model_validate(latest) if latest else None,
        recent_runs=[SyncLogRead.model_validate(r) for r in recent],
    )


@router.get("/logs", response_model=list[SyncLogRead], summary="Recent sync logs")
def sync_logs(
    limit: int = Query(50, ge=1, le=500),
    customer_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[SyncLogRead]:
    repo = SyncLogRepository(db)
    return [
        SyncLogRead.model_validate(r) for r in repo.recent(limit=limit, customer_id=customer_id)
    ]
