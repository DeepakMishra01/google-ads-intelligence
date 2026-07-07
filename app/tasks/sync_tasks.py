"""Callable sync tasks.

These are the units the scheduler and the manual-trigger endpoint invoke. Each
opens its own transactional session (never the request session) so it is safe to
run in a background thread. The heavy lifting and per-entity transaction control
live in :class:`SyncService`; this module only manages the session boundary.
"""

from __future__ import annotations

from datetime import date, datetime

from app.config.logging import get_logger
from app.database.session import session_scope
from app.schemas.sync import SyncRunResult
from app.services.sync_service import SyncService

log = get_logger(__name__)


def run_sync(
    *,
    customer_ids: list[str] | None = None,
    entity: str = "all",
    lookback_days: int | None = None,
    sync_type: str = "manual",
) -> SyncRunResult:
    """Run a sync in a fresh session and return the aggregate result."""
    with session_scope() as db:
        service = SyncService(db)
        result = service.run(
            customer_ids=customer_ids,
            entity=entity,
            lookback_days=lookback_days,
            sync_type=sync_type,
        )
    log.info(
        "sync.run.complete",
        entity=entity,
        sync_type=sync_type,
        status=result.status,
        inserted=result.rows_inserted,
        failed=result.rows_failed,
    )
    return result


def run_backfill(
    *,
    start_date: date,
    end_date: date,
    customer_ids: list[str] | None = None,
    entity: str = "all",
) -> SyncRunResult:
    """Backfill historical snapshots over a date range."""
    with session_scope() as db:
        service = SyncService(db)
        result = service.backfill(
            start_date=start_date,
            end_date=end_date,
            customer_ids=customer_ids,
            entity=entity,
        )
    log.info(
        "sync.backfill.complete",
        entity=entity,
        status=result.status,
        inserted=result.rows_inserted,
    )
    return result


def run_sync_safe(**kwargs: object) -> None:
    """Fire-and-forget wrapper for background threads / BackgroundTasks.

    Swallows and logs exceptions so a failed background sync can never crash the
    scheduler thread or leave a request handler in a bad state.
    """
    try:
        run_sync(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        log.error("sync.run.unhandled_error", error=str(exc), kwargs=str(kwargs))


def run_backfill_safe(**kwargs: object) -> None:
    """Fire-and-forget wrapper around :func:`run_backfill`."""
    try:
        run_backfill(**kwargs)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        log.error("sync.backfill.unhandled_error", error=str(exc), kwargs=str(kwargs))


# ---------------------------------------------------------------------------
# Scheduled entrypoints (bound to cron triggers in scheduler.py)
# ---------------------------------------------------------------------------
def hourly_sync() -> None:
    """Light hourly pulse: refresh recent campaign performance (2-day window)."""
    log.info("scheduler.hourly_sync.tick", at=datetime.now().isoformat())
    run_sync_safe(entity="campaigns", lookback_days=2, sync_type="hourly")


def daily_sync() -> None:
    """Full daily refresh: all entities over the default lookback window."""
    log.info("scheduler.daily_sync.tick", at=datetime.now().isoformat())
    run_sync_safe(entity="all", sync_type="daily")
