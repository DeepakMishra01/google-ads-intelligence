"""Campaign Explorer service - search campaigns by name over any date range."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.campaign_search import CampaignSearchRepository
from app.services.ops.dates import resolve_ref_dates


class CampaignSearchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CampaignSearchRepository(db)

    def search(
        self,
        *,
        q: str | None = None,
        account_id: int | None = None,
        days: int = 365,
        start: date | None = None,
        end: date | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        # Resolve the effective window: explicit range wins; a very large `days`
        # (the "All time" preset) spans the full data bounds; otherwise a rolling
        # window ending at the latest day with data.
        if start and end:
            s: date | None = start
            e: date | None = end
        else:
            lo, hi = self.repo.date_bounds()
            if days >= 1825 or lo is None:
                s, e = lo, hi
            else:
                s, e = resolve_ref_dates(self.db, account_id).window(days)

        rows, totals = self.repo.search(
            q=q, account_id=account_id, start=s, end=e, limit=limit
        )
        return {"items": rows, "totals": totals, "start": s, "end": e}
