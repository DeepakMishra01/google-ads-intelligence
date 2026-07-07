"""Trend Analytics service (Module 7)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.ops import OpsRepository
from app.services.ops.dates import resolve_ref_dates
from app.services.ops.scoring import pct_change

_METRICS = {"cost", "clicks", "impressions", "ctr", "avg_cpc", "conversions"}


class TrendService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OpsRepository(db)

    def _window(
        self, account_id: int | None, days: int, start: date | None, end: date | None
    ) -> tuple[date, date]:
        if start and end:
            return start, end
        return resolve_ref_dates(self.db, account_id).window(days)

    def metric_series(
        self,
        *,
        account_id: int | None = None,
        days: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        s, e = self._window(account_id, days, start, end)
        return self.repo.daily_series(s, e, account_id)

    def growth_series(
        self,
        *,
        account_id: int | None = None,
        days: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        s, e = self._window(account_id, days, start, end)
        return self.repo.daily_entity_counts(s, e, account_id)

    def compare_days(self, *, account_id: int | None = None) -> dict[str, Any]:
        """Latest day vs prior day, with per-metric deltas ("today vs yesterday")."""
        refs = resolve_ref_dates(self.db, account_id)
        latest = self.repo.account_day_totals(refs.latest, account_id)
        prior = self.repo.account_day_totals(refs.prior, account_id)

        def derived(t: dict[str, Any]) -> dict[str, Any]:
            ctr = (t["clicks"] / t["impressions"]) if t["impressions"] else None
            cpc = (t["cost"] / t["clicks"]) if t["clicks"] else None
            return {**t, "ctr": ctr, "avg_cpc": cpc}

        cur, prev = derived(latest), derived(prior)
        deltas: dict[str, float] = {}
        for m in ("cost", "clicks", "impressions", "ctr", "avg_cpc"):
            if cur[m] is None or prev[m] is None:
                continue
            change = pct_change(cur[m], prev[m])
            if change is not None:
                deltas[m] = change
        return {
            "latest_date": refs.latest,
            "prior_date": refs.prior,
            "latest": cur,
            "prior": prev,
            "deltas": deltas,
        }
