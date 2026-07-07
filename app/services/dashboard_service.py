"""Dashboard service: date-window resolution + delegation to aggregate queries."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.dashboard import DashboardRepository


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.repo = DashboardRepository(db)

    @staticmethod
    def _window(days: int) -> tuple[date, date]:
        end = date.today()
        return end - timedelta(days=max(0, days - 1)), end

    def top_spending_campaigns(
        self, *, account_id: int | None, days: int, limit: int
    ) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.top_spending_campaigns(
            start=start, end=end, account_id=account_id, limit=limit
        )

    def highest_cpc_campaigns(
        self, *, account_id: int | None, days: int, limit: int
    ) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.highest_cpc_campaigns(
            start=start, end=end, account_id=account_id, limit=limit
        )

    def lowest_ctr_campaigns(
        self, *, account_id: int | None, days: int, limit: int
    ) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.lowest_ctr_campaigns(
            start=start, end=end, account_id=account_id, limit=limit
        )

    def campaign_health(self, *, account_id: int | None, days: int) -> list[dict[str, Any]]:
        start, end = self._window(days)
        rows = self.repo.campaign_aggregates(start=start, end=end, account_id=account_id)
        rows.sort(key=lambda x: x["cost"], reverse=True)
        return rows

    def keyword_health(
        self, *, account_id: int | None, days: int, limit: int
    ) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.keyword_health(start=start, end=end, account_id=account_id, limit=limit)

    def search_term_report(
        self, *, account_id: int | None, days: int, limit: int
    ) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.search_term_report(
            start=start, end=end, account_id=account_id, limit=limit
        )

    def budget_utilization(self, *, account_id: int | None) -> list[dict[str, Any]]:
        return self.repo.budget_utilization(account_id=account_id)

    def daily_spend_trend(self, *, account_id: int | None, days: int) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.daily_spend_trend(start=start, end=end, account_id=account_id)

    def campaign_trend(self, *, campaign_pk: int, days: int) -> list[dict[str, Any]]:
        start, end = self._window(days)
        return self.repo.campaign_trend(campaign_pk=campaign_pk, start=start, end=end)
