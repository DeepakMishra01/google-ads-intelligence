"""APScheduler wiring for hourly / daily syncs.

The scheduler runs in-process (BackgroundScheduler) inside the API container.
For a single-worker deployment this is the simplest reliable option. If the API
is scaled to multiple workers, run the scheduler as its own single-replica
service (``python -m app.tasks.scheduler``) so jobs are not duplicated - the job
functions themselves are process-agnostic. Celery can replace this module wholesale
without touching SyncService.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.tasks.sync_tasks import daily_sync, hourly_sync

log = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def create_scheduler() -> BackgroundScheduler:
    """Build a scheduler with the configured cron jobs (not started)."""
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")

    if settings.sync_hourly_enabled:
        scheduler.add_job(
            hourly_sync,
            CronTrigger(minute=0),  # top of every hour
            id="hourly_sync",
            name="Hourly campaign performance sync",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
            replace_existing=True,
        )

    if settings.sync_daily_enabled:
        scheduler.add_job(
            daily_sync,
            CronTrigger(hour=settings.sync_daily_hour, minute=15),
            id="daily_sync",
            name="Daily full sync",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            replace_existing=True,
        )
    return scheduler


def start_scheduler() -> BackgroundScheduler | None:
    """Start the process-wide scheduler if enabled. Idempotent."""
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        log.info("scheduler.disabled")
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    jobs = [f"{j.id}@{j.next_run_time}" for j in _scheduler.get_jobs()]
    log.info("scheduler.started", jobs=jobs)
    return _scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler on application shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
    _scheduler = None


if __name__ == "__main__":  # run the scheduler standalone
    import time

    sched = start_scheduler()
    if sched is None:
        raise SystemExit("Scheduler is disabled (SCHEDULER_ENABLED=false).")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        shutdown_scheduler()
