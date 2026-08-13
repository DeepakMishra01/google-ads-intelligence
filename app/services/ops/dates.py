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
    """Return the latest and prior snapshot dates — anchored to the GLOBAL freshest
    day any account has data for, not the selected account's own latest.

    Why global: a dormant account's most recent snapshot may be months old (its last
    active day). Anchoring 'last N days' to that stale date shows old data and makes
    the account look active when it isn't. Anchoring to the freshest day across all
    accounts means a dormant account correctly reports ~0 for the recent window,
    matching Google Ads. (``account_id`` is accepted for call-site compatibility but
    intentionally does not narrow the anchor date.)
    """
    latest = db.execute(
        select(func.max(CampaignSnapshot.snapshot_date))
    ).scalar_one_or_none()
    if latest is None:
        latest = date.today() - timedelta(days=1)
    return RefDates(latest=latest, prior=latest - timedelta(days=1))


def fraction_of_day_elapsed(now: datetime | None = None) -> float:
    """Fraction of the current UTC day elapsed (for end-of-day projections)."""
    now = now or datetime.utcnow()
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    return seconds / 86_400
