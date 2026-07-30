"""Weekly scorecard snapshotting.

For every campus that has a saved plan, compute and persist a scorecard snapshot
so results are tracked week-over-week and each report compares against the prior
one. Opens its own session (safe for the scheduler thread) and never lets one
campus's failure stop the others.
"""

from __future__ import annotations

from datetime import datetime

from app.config.logging import get_logger
from app.database.session import session_scope
from app.repositories.ad_copy import ScorecardSnapshotRepository
from app.services.ai.ad_copy_service import AdCopyService

log = get_logger(__name__)


def snapshot_all_scorecards() -> int:
    """Save a scorecard snapshot for each campus with a saved plan. Returns count."""
    saved = 0
    with session_scope() as db:
        campuses = ScorecardSnapshotRepository(db).distinct_campuses()
        svc = AdCopyService(db)
        for campus in campuses:
            try:
                res = svc.save_scorecard(campus=campus)
                saved += 1 if res.get("saved") else 0
            except Exception as exc:  # noqa: BLE001 — one campus must not stop the rest
                log.error("scorecard.snapshot.failed", campus=campus, error=str(exc))
                db.rollback()
    return saved


def weekly_scorecard() -> None:
    """Scheduled entrypoint (bound to a weekly cron in scheduler.py)."""
    log.info("scheduler.weekly_scorecard.tick", at=datetime.now().isoformat())
    try:
        n = snapshot_all_scorecards()
        log.info("scheduler.weekly_scorecard.done", snapshots=n)
    except Exception as exc:  # noqa: BLE001
        log.error("scheduler.weekly_scorecard.unhandled_error", error=str(exc))
