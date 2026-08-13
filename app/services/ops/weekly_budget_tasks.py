"""Weekly budget summary email to admins (Monday, for the week just ended)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.services.ops.weekly_budget_service import WeeklyBudgetService

log = get_logger(__name__)


def _admin_recipients(db: Session) -> str:
    from app.models.user import User, UserRole

    s = get_settings()
    emails = {
        e.strip().lower()
        for e in db.execute(
            select(User.email).where(
                User.role == UserRole.ADMIN.value, User.is_active.is_(True)
            )
        ).scalars()
        if e and e.strip()
    }
    emails |= set(s.admin_emails_list)
    if emails:
        return ", ".join(sorted(emails))
    return s.approval_reviewer_email or ""


def send_weekly_budget_email(db: Session) -> dict[str, Any]:
    from app.services.ai.email_service import send_email

    to = _admin_recipients(db)
    if not to:
        return {"sent": False, "reason": "No admin recipients configured."}
    subject, text, html = WeeklyBudgetService(db).weekly_email_html()
    return send_email(to=to, subject=subject, body=text, html=html)


def weekly_budget_job() -> None:
    """APScheduler entrypoint — opens its own session."""
    from app.database.session import session_scope

    try:
        with session_scope() as db:
            result = send_weekly_budget_email(db)
        log.info("weekly_budget.email", **{k: v for k, v in result.items() if k != "reason"})
    except Exception as exc:  # noqa: BLE001 — never crash the scheduler
        log.warning("weekly_budget.email_failed", error=str(exc))
