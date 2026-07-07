"""Aggregate queries for the Operations Command Center.

Every method issues a small number of set-based, grouped queries (never per-row
lookups) and returns plain dicts keyed by entity PK, so services can merge them
in memory without N+1 round-trips. Monetary values are converted from micros to
account-currency units here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ad import Ad
from app.models.ad_group import AdGroup
from app.models.budget import Budget, BudgetSnapshot
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword, KeywordSnapshot
from app.models.search_term import SearchTerm, SearchTermSnapshot

_MICROS = 1_000_000
_ACTIVE = "ENABLED"


class OpsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Overview counts
    # ------------------------------------------------------------------ #
    def _count(self, model: Any, *conditions: Any) -> int:
        stmt = select(func.count()).select_from(model)
        for cond in conditions:
            stmt = stmt.where(cond)
        return int(self.db.execute(stmt).scalar_one())

    def entity_counts(self, account_id: int | None) -> dict[str, int]:
        acc_cond = []
        if account_id is not None:
            acc_cond = [Account.id == account_id]
        return {
            "accounts": self._count(Account, Account.is_manager.is_(False), *acc_cond),
            "campaigns_active": self._count(
                Campaign,
                Campaign.status == _ACTIVE,
                *([Campaign.account_id == account_id] if account_id else []),
            ),
            "ad_groups_active": self._count(
                AdGroup,
                AdGroup.status == _ACTIVE,
                *([AdGroup.account_id == account_id] if account_id else []),
            ),
            "keywords_active": self._count(
                Keyword,
                Keyword.status == _ACTIVE,
                *([Keyword.account_id == account_id] if account_id else []),
            ),
        }

    def account_day_totals(self, day: date, account_id: int | None) -> dict[str, float]:
        stmt = select(
            func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
            func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
            func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
            func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
        ).where(CampaignSnapshot.snapshot_date == day)
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        impressions, clicks, cost_micros, conversions = self.db.execute(stmt).one()
        return {
            "impressions": int(impressions),
            "clicks": int(clicks),
            "cost": round(float(cost_micros) / _MICROS, 2),
            "conversions": float(conversions),
        }

    def new_search_terms_count(self, day: date, account_id: int | None) -> int:
        stmt = select(func.count(SearchTerm.id)).where(
            cast(SearchTerm.created_at, Date) == day
        )
        if account_id is not None:
            stmt = stmt.where(SearchTerm.account_id == account_id)
        return int(self.db.execute(stmt).scalar_one())

    def low_quality_keyword_count(self, day: date, floor: int, account_id: int | None) -> int:
        stmt = select(func.count(func.distinct(KeywordSnapshot.keyword_id))).where(
            KeywordSnapshot.snapshot_date == day,
            KeywordSnapshot.quality_score.is_not(None),
            KeywordSnapshot.quality_score < floor,
        )
        if account_id is not None:
            stmt = stmt.where(KeywordSnapshot.account_id == account_id)
        return int(self.db.execute(stmt).scalar_one())

    def campaigns_limited_by_budget_count(self, day: date, account_id: int | None) -> int:
        stmt = select(func.count(CampaignSnapshot.id)).where(
            CampaignSnapshot.snapshot_date == day,
            CampaignSnapshot.budget_micros.is_not(None),
            CampaignSnapshot.budget_micros > 0,
            CampaignSnapshot.cost_micros >= CampaignSnapshot.budget_micros,
        )
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        return int(self.db.execute(stmt).scalar_one())

    # ------------------------------------------------------------------ #
    # Campaign health inputs (grouped; merged by the service)
    # ------------------------------------------------------------------ #
    def campaign_metrics_by_day(
        self, days: list[date], account_id: int | None
    ) -> dict[tuple[int, date], dict[str, Any]]:
        """Return {(campaign_pk, day): metrics} for the requested days."""
        stmt = (
            select(
                CampaignSnapshot.campaign_id,
                CampaignSnapshot.snapshot_date,
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0).label("conversions"),
                func.max(CampaignSnapshot.budget_micros).label("budget_micros"),
            )
            .where(CampaignSnapshot.snapshot_date.in_(days))
            .group_by(CampaignSnapshot.campaign_id, CampaignSnapshot.snapshot_date)
        )
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        out: dict[tuple[int, date], dict[str, Any]] = {}
        for r in self.db.execute(stmt).mappings():
            out[(r["campaign_id"], r["snapshot_date"])] = {
                "impressions": int(r["impressions"]),
                "clicks": int(r["clicks"]),
                "cost": float(r["cost_micros"]) / _MICROS,
                "conversions": float(r["conversions"]),
                "budget": (float(r["budget_micros"]) / _MICROS) if r["budget_micros"] else 0.0,
            }
        return out

    def campaign_meta(self, account_id: int | None) -> dict[int, dict[str, Any]]:
        stmt = select(
            Campaign.id,
            Campaign.campaign_id,
            Campaign.name,
            Campaign.account_id,
            Campaign.status,
            Campaign.optimization_score,
        )
        if account_id is not None:
            stmt = stmt.where(Campaign.account_id == account_id)
        return {
            r["id"]: {
                "campaign_pk": r["id"],
                "campaign_id": r["campaign_id"],
                "name": r["name"],
                "account_id": r["account_id"],
                "status": r["status"],
                "optimization_score": (
                    float(r["optimization_score"]) if r["optimization_score"] is not None else None
                ),
            }
            for r in self.db.execute(stmt).mappings()
        }

    def avg_quality_score_by_campaign(
        self, day: date, account_id: int | None
    ) -> dict[int, float]:
        stmt = (
            select(
                KeywordSnapshot.campaign_id,
                func.avg(KeywordSnapshot.quality_score),
            )
            .where(
                KeywordSnapshot.snapshot_date == day,
                KeywordSnapshot.quality_score.is_not(None),
            )
            .group_by(KeywordSnapshot.campaign_id)
        )
        if account_id is not None:
            stmt = stmt.where(KeywordSnapshot.account_id == account_id)
        return {cid: float(avg) for cid, avg in self.db.execute(stmt).all() if avg is not None}

    def disapproved_ads_by_campaign(self, account_id: int | None) -> dict[int, int]:
        """Disapproved ad counts per campaign, from current ad dimension state."""
        stmt = (
            select(AdGroup.campaign_id, func.count(Ad.id))
            .join(AdGroup, Ad.ad_group_id == AdGroup.id)
            .where(Ad.approval_status == "DISAPPROVED", Ad.status != "REMOVED")
            .group_by(AdGroup.campaign_id)
        )
        if account_id is not None:
            stmt = stmt.where(Ad.account_id == account_id)
        return {cid: int(n) for cid, n in self.db.execute(stmt).all()}

    # ------------------------------------------------------------------ #
    # Keyword health inputs
    # ------------------------------------------------------------------ #
    def keyword_metrics(
        self, start: date, end: date, account_id: int | None, cap: int = 5000
    ) -> list[dict[str, Any]]:
        """Aggregate keyword performance + avg quality score over a window."""
        stmt = (
            select(
                Keyword.id.label("keyword_pk"),
                Keyword.text,
                Keyword.match_type,
                Keyword.account_id,
                KeywordSnapshot.campaign_id,
                func.avg(KeywordSnapshot.quality_score).label("quality_score"),
                func.coalesce(func.sum(KeywordSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(KeywordSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(KeywordSnapshot.conversions), 0).label("conversions"),
            )
            .join(KeywordSnapshot, KeywordSnapshot.keyword_id == Keyword.id)
            .where(KeywordSnapshot.snapshot_date.between(start, end))
            .group_by(
                Keyword.id,
                Keyword.text,
                Keyword.match_type,
                Keyword.account_id,
                KeywordSnapshot.campaign_id,
            )
            .limit(cap)
        )
        if account_id is not None:
            stmt = stmt.where(Keyword.account_id == account_id)
        out: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            qs = r["quality_score"]
            out.append(
                {
                    "keyword_pk": r["keyword_pk"],
                    "text": r["text"],
                    "match_type": r["match_type"],
                    "account_id": r["account_id"],
                    "campaign_id": r["campaign_id"],
                    "quality_score": round(float(qs)) if qs is not None else None,
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                    "cost": round(float(r["cost_micros"]) / _MICROS, 2),
                    "conversions": float(r["conversions"]),
                }
            )
        return out

    # ------------------------------------------------------------------ #
    # Search Term Explorer (Module 4)
    # ------------------------------------------------------------------ #
    def search_terms_explore(
        self,
        *,
        start: date,
        end: date,
        account_id: int | None = None,
        campaign_id: int | None = None,
        ad_group_id: int | None = None,
        min_clicks: int = 0,
        min_cost: float = 0.0,
        min_ctr: float | None = None,
        contains: str | None = None,
        sort: str = "cost",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clicks_sum = func.coalesce(func.sum(SearchTermSnapshot.clicks), 0)
        impr_sum = func.coalesce(func.sum(SearchTermSnapshot.impressions), 0)
        cost_sum = func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0)
        conv_sum = func.coalesce(func.sum(SearchTermSnapshot.conversions), 0)

        base = (
            select(
                SearchTerm.id.label("search_term_pk"),
                SearchTerm.query,
                SearchTerm.search_term_targeting_status.label("status"),
                Campaign.name.label("campaign_name"),
                AdGroup.name.label("ad_group_name"),
                clicks_sum.label("clicks"),
                impr_sum.label("impressions"),
                cost_sum.label("cost_micros"),
                conv_sum.label("conversions"),
            )
            .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
            .join(Campaign, SearchTerm.campaign_id == Campaign.id)
            .join(AdGroup, SearchTerm.ad_group_id == AdGroup.id)
            .where(SearchTermSnapshot.snapshot_date.between(start, end))
            .group_by(
                SearchTerm.id,
                SearchTerm.query,
                SearchTerm.search_term_targeting_status,
                Campaign.name,
                AdGroup.name,
            )
        )
        if account_id is not None:
            base = base.where(SearchTerm.account_id == account_id)
        if campaign_id is not None:
            base = base.where(SearchTerm.campaign_id == campaign_id)
        if ad_group_id is not None:
            base = base.where(SearchTerm.ad_group_id == ad_group_id)
        if contains:
            base = base.where(SearchTerm.query.ilike(f"%{contains}%"))

        havings = []
        if min_clicks:
            havings.append(clicks_sum >= min_clicks)
        if min_cost:
            havings.append(cost_sum >= int(min_cost * _MICROS))
        if min_ctr is not None:
            # clicks / impressions >= min_ctr, guarding divide-by-zero.
            havings.append(clicks_sum >= min_ctr * impr_sum)
        for h in havings:
            base = base.having(h)

        # Total distinct groups (for pagination).
        total = int(
            self.db.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
        )

        sort_cols = {
            "cost": cost_sum.desc(),
            "clicks": clicks_sum.desc(),
            "impressions": impr_sum.desc(),
            "conversions": conv_sum.desc(),
        }
        stmt = base.order_by(sort_cols.get(sort, cost_sum.desc())).offset(offset).limit(limit)

        rows: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            clicks = int(r["clicks"])
            impressions = int(r["impressions"])
            cost = round(float(r["cost_micros"]) / _MICROS, 2)
            rows.append(
                {
                    "search_term_pk": r["search_term_pk"],
                    "query": r["query"],
                    "status": r["status"],
                    "campaign_name": r["campaign_name"],
                    "ad_group_name": r["ad_group_name"],
                    "clicks": clicks,
                    "impressions": impressions,
                    "cost": cost,
                    "conversions": float(r["conversions"]),
                    "ctr": (clicks / impressions) if impressions else None,
                    "avg_cpc": (cost / clicks) if clicks else None,
                }
            )
        return rows, total

    # ------------------------------------------------------------------ #
    # Trend series
    # ------------------------------------------------------------------ #
    def daily_series(
        self, start: date, end: date, account_id: int | None
    ) -> list[dict[str, Any]]:
        """Per-day account totals with derived CTR/CPC over a window."""
        stmt = (
            select(
                CampaignSnapshot.snapshot_date.label("d"),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0).label("impressions"),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0).label("clicks"),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0).label("cost_micros"),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0).label("conversions"),
            )
            .where(CampaignSnapshot.snapshot_date.between(start, end))
            .group_by(CampaignSnapshot.snapshot_date)
            .order_by(CampaignSnapshot.snapshot_date)
        )
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        out: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            impressions = int(r["impressions"])
            clicks = int(r["clicks"])
            cost = round(float(r["cost_micros"]) / _MICROS, 2)
            out.append(
                {
                    "date": r["d"],
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "conversions": float(r["conversions"]),
                    "ctr": (clicks / impressions) if impressions else None,
                    "avg_cpc": (cost / clicks) if clicks else None,
                }
            )
        return out

    def daily_entity_counts(
        self, start: date, end: date, account_id: int | None
    ) -> list[dict[str, Any]]:
        """Per-day distinct active campaign/keyword/search-term counts (growth)."""

        def _counts(model: Any, id_col: Any) -> dict[date, int]:
            stmt = (
                select(model.snapshot_date, func.count(func.distinct(id_col)))
                .where(model.snapshot_date.between(start, end))
                .group_by(model.snapshot_date)
            )
            if account_id is not None:
                stmt = stmt.where(model.account_id == account_id)
            return {d: int(n) for d, n in self.db.execute(stmt).all()}

        campaigns = _counts(CampaignSnapshot, CampaignSnapshot.campaign_id)
        keywords = _counts(KeywordSnapshot, KeywordSnapshot.keyword_id)
        terms = _counts(SearchTermSnapshot, SearchTermSnapshot.search_term_id)
        all_days = sorted(set(campaigns) | set(keywords) | set(terms))
        return [
            {
                "date": d,
                "campaigns": campaigns.get(d, 0),
                "keywords": keywords.get(d, 0),
                "search_terms": terms.get(d, 0),
            }
            for d in all_days
        ]

    # ------------------------------------------------------------------ #
    # Budget inputs
    # ------------------------------------------------------------------ #
    def latest_budget_snapshots(self, account_id: int | None) -> list[dict[str, Any]]:
        stmt = (
            select(
                Budget.id.label("budget_pk"),
                Budget.name,
                Budget.account_id,
                BudgetSnapshot.snapshot_date,
                BudgetSnapshot.amount_micros,
                BudgetSnapshot.spend_micros,
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
                }
            )
        return out
