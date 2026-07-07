"""Read-optimized aggregate queries powering the dashboard endpoints.

These queries are intentionally written to be database-portable (they compute
ratios in Python rather than relying on dialect-specific SQL) so the same code
runs against Postgres in production and SQLite in tests. For the data volumes in
Phase 1 (hundreds of campaigns per account) this is more than fast enough; the
snapshot tables are indexed on ``snapshot_date`` and ``account_id`` for the
range scans below.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget, BudgetSnapshot
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword, KeywordSnapshot
from app.models.search_term import SearchTerm, SearchTermSnapshot

_MICROS = 1_000_000


def _ratio(numerator: float, denominator: float) -> float | None:
    return (numerator / denominator) if denominator else None


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Campaign aggregates
    # ------------------------------------------------------------------ #
    def campaign_aggregates(
        self, *, start: date, end: date, account_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Sum campaign metrics over a date window; one row per campaign."""
        stmt = (
            select(
                Campaign.id.label("campaign_pk"),
                Campaign.campaign_id.label("campaign_id"),
                Campaign.name.label("campaign_name"),
                Campaign.account_id.label("account_id"),
                Campaign.status.label("status"),
                Campaign.optimization_score.label("optimization_score"),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0).label("conversions"),
            )
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
            .where(CampaignSnapshot.snapshot_date.between(start, end))
            .group_by(
                Campaign.id,
                Campaign.campaign_id,
                Campaign.name,
                Campaign.account_id,
                Campaign.status,
                Campaign.optimization_score,
            )
        )
        if account_id is not None:
            stmt = stmt.where(Campaign.account_id == account_id)

        results: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            clicks = float(r["clicks"])
            impressions = float(r["impressions"])
            cost = float(r["cost_micros"]) / _MICROS
            results.append(
                {
                    "campaign_pk": r["campaign_pk"],
                    "campaign_id": r["campaign_id"],
                    "campaign_name": r["campaign_name"],
                    "account_id": r["account_id"],
                    "status": r["status"],
                    "optimization_score": (
                        float(r["optimization_score"])
                        if r["optimization_score"] is not None
                        else None
                    ),
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                    "cost": round(cost, 2),
                    "conversions": float(r["conversions"]),
                    "ctr": _ratio(clicks, impressions),
                    "avg_cpc": _ratio(cost, clicks),
                    "cost_per_conversion": _ratio(cost, float(r["conversions"])),
                }
            )
        return results

    def top_spending_campaigns(
        self, *, start: date, end: date, account_id: int | None, limit: int
    ) -> list[dict[str, Any]]:
        rows = self.campaign_aggregates(start=start, end=end, account_id=account_id)
        rows.sort(key=lambda x: x["cost"], reverse=True)
        return rows[:limit]

    def highest_cpc_campaigns(
        self, *, start: date, end: date, account_id: int | None, limit: int
    ) -> list[dict[str, Any]]:
        rows = [
            r
            for r in self.campaign_aggregates(start=start, end=end, account_id=account_id)
            if r["avg_cpc"] is not None
        ]
        rows.sort(key=lambda x: x["avg_cpc"], reverse=True)
        return rows[:limit]

    def lowest_ctr_campaigns(
        self,
        *,
        start: date,
        end: date,
        account_id: int | None,
        limit: int,
        min_impressions: int = 100,
    ) -> list[dict[str, Any]]:
        rows = [
            r
            for r in self.campaign_aggregates(start=start, end=end, account_id=account_id)
            if r["ctr"] is not None and r["impressions"] >= min_impressions
        ]
        rows.sort(key=lambda x: x["ctr"])
        return rows[:limit]

    # ------------------------------------------------------------------ #
    # Keyword & search term health
    # ------------------------------------------------------------------ #
    def keyword_health(
        self, *, start: date, end: date, account_id: int | None, limit: int
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Keyword.id.label("keyword_pk"),
                Keyword.text.label("text"),
                Keyword.match_type.label("match_type"),
                Keyword.account_id.label("account_id"),
                func.avg(KeywordSnapshot.quality_score).label("avg_quality_score"),
                func.coalesce(func.sum(KeywordSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(KeywordSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(KeywordSnapshot.conversions), 0).label("conversions"),
            )
            .join(KeywordSnapshot, KeywordSnapshot.keyword_id == Keyword.id)
            .where(KeywordSnapshot.snapshot_date.between(start, end))
            .group_by(Keyword.id, Keyword.text, Keyword.match_type, Keyword.account_id)
        )
        if account_id is not None:
            stmt = stmt.where(Keyword.account_id == account_id)

        out: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            clicks = float(r["clicks"])
            impressions = float(r["impressions"])
            cost = float(r["cost_micros"]) / _MICROS
            out.append(
                {
                    "keyword_pk": r["keyword_pk"],
                    "text": r["text"],
                    "match_type": r["match_type"],
                    "account_id": r["account_id"],
                    "avg_quality_score": (
                        round(float(r["avg_quality_score"]), 2)
                        if r["avg_quality_score"] is not None
                        else None
                    ),
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                    "cost": round(cost, 2),
                    "conversions": float(r["conversions"]),
                    "ctr": _ratio(clicks, impressions),
                    "avg_cpc": _ratio(cost, clicks),
                }
            )
        # Worst quality first (nulls last), then by spend.
        out.sort(
            key=lambda x: (x["avg_quality_score"] is None, x["avg_quality_score"] or 0, -x["cost"])
        )
        return out[:limit]

    def search_term_report(
        self, *, start: date, end: date, account_id: int | None, limit: int
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                SearchTerm.id.label("search_term_pk"),
                SearchTerm.query.label("query"),
                SearchTerm.account_id.label("account_id"),
                func.coalesce(func.sum(SearchTermSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(SearchTermSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(SearchTermSnapshot.conversions), 0).label("conversions"),
            )
            .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
            .where(SearchTermSnapshot.snapshot_date.between(start, end))
            .group_by(SearchTerm.id, SearchTerm.query, SearchTerm.account_id)
        )
        if account_id is not None:
            stmt = stmt.where(SearchTerm.account_id == account_id)

        out: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            clicks = float(r["clicks"])
            impressions = float(r["impressions"])
            cost = float(r["cost_micros"]) / _MICROS
            out.append(
                {
                    "search_term_pk": r["search_term_pk"],
                    "query": r["query"],
                    "account_id": r["account_id"],
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                    "cost": round(cost, 2),
                    "conversions": float(r["conversions"]),
                    "ctr": _ratio(clicks, impressions),
                }
            )
        out.sort(key=lambda x: x["cost"], reverse=True)
        return out[:limit]

    # ------------------------------------------------------------------ #
    # Budget utilization & spend trends
    # ------------------------------------------------------------------ #
    def budget_utilization(
        self, *, account_id: int | None, lookback_days: int = 14
    ) -> list[dict[str, Any]]:
        """Latest snapshot per budget within the lookback window."""
        stmt = (
            select(
                Budget.id.label("budget_pk"),
                Budget.name.label("name"),
                Budget.account_id.label("account_id"),
                BudgetSnapshot.snapshot_date.label("snapshot_date"),
                BudgetSnapshot.amount_micros.label("amount_micros"),
                BudgetSnapshot.spend_micros.label("spend_micros"),
                BudgetSnapshot.utilization.label("utilization"),
            )
            .join(BudgetSnapshot, BudgetSnapshot.budget_id == Budget.id)
            .order_by(BudgetSnapshot.snapshot_date.desc())
        )
        if account_id is not None:
            stmt = stmt.where(Budget.account_id == account_id)

        seen: set[int] = set()
        out: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            if r["budget_pk"] in seen:
                continue
            seen.add(r["budget_pk"])
            out.append(
                {
                    "budget_pk": r["budget_pk"],
                    "name": r["name"],
                    "account_id": r["account_id"],
                    "snapshot_date": r["snapshot_date"],
                    "amount": round(float(r["amount_micros"] or 0) / _MICROS, 2),
                    "spend": round(float(r["spend_micros"] or 0) / _MICROS, 2),
                    "utilization": (
                        float(r["utilization"]) if r["utilization"] is not None else None
                    ),
                }
            )
        return out

    def daily_spend_trend(
        self, *, start: date, end: date, account_id: int | None
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                CampaignSnapshot.snapshot_date.label("snapshot_date"),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0).label("conversions"),
            )
            .where(CampaignSnapshot.snapshot_date.between(start, end))
            .group_by(CampaignSnapshot.snapshot_date)
            .order_by(CampaignSnapshot.snapshot_date)
        )
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        return [
            {
                "date": r["snapshot_date"],
                "cost": round(float(r["cost_micros"]) / _MICROS, 2),
                "clicks": int(r["clicks"]),
                "impressions": int(r["impressions"]),
                "conversions": float(r["conversions"]),
            }
            for r in self.db.execute(stmt).mappings()
        ]

    def campaign_trend(self, *, campaign_pk: int, start: date, end: date) -> list[dict[str, Any]]:
        stmt = (
            select(CampaignSnapshot)
            .where(
                CampaignSnapshot.campaign_id == campaign_pk,
                CampaignSnapshot.snapshot_date.between(start, end),
            )
            .order_by(CampaignSnapshot.snapshot_date)
        )
        out: list[dict[str, Any]] = []
        for s in self.db.execute(stmt).scalars():
            cost = float(s.cost_micros) / _MICROS
            out.append(
                {
                    "date": s.snapshot_date,
                    "impressions": s.impressions,
                    "clicks": s.clicks,
                    "cost": round(cost, 2),
                    "conversions": float(s.conversions),
                    "ctr": _ratio(float(s.clicks), float(s.impressions)),
                    "avg_cpc": _ratio(cost, float(s.clicks)),
                }
            )
        return out
