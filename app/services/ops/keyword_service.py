"""Keyword Health service (Module 5)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config.ops_rules import get_ops_rules
from app.repositories.ops import OpsRepository
from app.services.ops.dates import resolve_ref_dates
from app.services.ops.scoring import DayMetrics, KeywordContext, compute_keyword_health

# Sort strategies -> key function (negative == descending).
_SORTS = {
    "worst": lambda r: r["health_score"],
    "highest_spend": lambda r: -r["cost"],
    "lowest_ctr": lambda r: (r["ctr"] is None, r["ctr"] or 0),
    "highest_cpc": lambda r: -(r["avg_cpc"] or 0),
    "lowest_quality_score": lambda r: (r["quality_score"] is None, r["quality_score"] or 0),
}


class KeywordHealthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OpsRepository(db)
        self.rules = get_ops_rules()

    def health(
        self,
        *,
        account_id: int | None = None,
        days: int = 30,
        sort: str = "worst",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        refs = resolve_ref_dates(self.db, account_id)
        start, end = refs.window(days)
        rows: list[dict[str, Any]] = []
        for k in self.repo.keyword_metrics(start, end, account_id):
            metrics = DayMetrics(
                impressions=k["impressions"],
                clicks=k["clicks"],
                cost=k["cost"],
                conversions=k["conversions"],
            )
            ctx = KeywordContext(
                quality_score=k["quality_score"],
                cost=k["cost"],
                conversions=k["conversions"],
                metrics=metrics,
            )
            result = compute_keyword_health(ctx, self.rules.keyword)
            rows.append(
                {
                    "keyword_pk": k["keyword_pk"],
                    "text": k["text"],
                    "match_type": k["match_type"],
                    "account_id": k["account_id"],
                    "campaign_id": k["campaign_id"],
                    "quality_score": k["quality_score"],
                    "impressions": k["impressions"],
                    "clicks": k["clicks"],
                    "cost": k["cost"],
                    "conversions": k["conversions"],
                    "ctr": metrics.ctr,
                    "avg_cpc": metrics.avg_cpc,
                    "health_score": result.score,
                    "health_level": result.level,
                    "issues": [i.label for i in result.issues],
                    # Populated by the Phase 3 recommendation engine.
                    "recommendation": None,
                }
            )
        rows.sort(key=_SORTS.get(sort, _SORTS["worst"]))
        return rows[:limit]
