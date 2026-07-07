"""Search Term Explorer service (Module 4)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.ops import OpsRepository
from app.services.ops.dates import resolve_ref_dates


class SearchExplorerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OpsRepository(db)

    def explore(
        self,
        *,
        account_id: int | None = None,
        campaign_id: int | None = None,
        ad_group_id: int | None = None,
        days: int = 30,
        start: date | None = None,
        end: date | None = None,
        min_clicks: int = 0,
        min_cost: float = 0.0,
        min_ctr: float | None = None,
        contains: str | None = None,
        sort: str = "cost",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not (start and end):
            start, end = resolve_ref_dates(self.db, account_id).window(days)
        return self.repo.search_terms_explore(
            start=start,
            end=end,
            account_id=account_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            min_clicks=min_clicks,
            min_cost=min_cost,
            min_ctr=min_ctr,
            contains=contains,
            sort=sort,
            limit=limit,
            offset=offset,
        )
