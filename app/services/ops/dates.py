"""Reference-date resolution for the Command Center.

Phase 1 syncs complete days (the current calendar day's metrics are still
accumulating), so "today" operationally means *the latest day we have data for*.
Resolving dates from the data - rather than the wall clock - makes day-over-day
comparisons correct regardless of when the last sync ran.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import CampaignSnapshot


@dataclass(frozen=True)
class RefDates:
    latest: date  # most recent day with data ("today")
    prior: date  # the day before ("yesterday")

    def window(self, days: int) -> tuple[date, date]:
        """Inclusive (start, end) window of ``days`` ending at ``latest``."""
        return self.latest - timedelta(days=max(0, days - 1)), self.latest


def resolve_ref_dates(db: Session, account_id: int | None = None) -> RefDates:
    """Return the latest and prior snapshot dates, falling back to the calendar."""
    stmt = select(func.max(CampaignSnapshot.snapshot_date))
    if account_id is not None:
        stmt = stmt.where(CampaignSnapshot.account_id == account_id)
    latest = db.execute(stmt).scalar_one_or_none()
    if latest is None:
        latest = date.today() - timedelta(days=1)
    return RefDates(latest=latest, prior=latest - timedelta(days=1))


def fraction_of_day_elapsed(now: datetime | None = None) -> float:
    """Fraction of the current UTC day elapsed (for end-of-day projections)."""
    now = now or datetime.utcnow()
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    return seconds / 86_400
