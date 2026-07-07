"""Campaign analyzer - builds health + priority for every campaign in one pass.

This is the shared engine behind ``/campaigns/health``, ``/dashboard/priorities``,
the executive overview, and the campaign portion of the alert engine. It performs
a fixed, small number of grouped queries (via :class:`OpsRepository`) and merges
them in memory - no per-campaign queries.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config.ops_rules import OpsRules, get_ops_rules
from app.repositories.ops import OpsRepository
from app.services.ops.dates import RefDates, resolve_ref_dates
from app.services.ops.scoring import (
    CampaignContext,
    DayMetrics,
    HealthResult,
    PriorityResult,
    compute_campaign_health,
    compute_priority,
)


@dataclass
class CampaignAnalysis:
    campaign_pk: int
    campaign_id: int
    name: str | None
    account_id: int
    status: str | None
    daily_budget: float
    spend_today: float
    spend_yesterday: float
    budget_utilization: float | None
    optimization_score: float | None
    today: DayMetrics
    prior: DayMetrics
    health: HealthResult
    priority: PriorityResult


class CampaignAnalyzer:
    def __init__(self, db: Session, rules: OpsRules | None = None) -> None:
        self.db = db
        self.repo = OpsRepository(db)
        self.rules = rules or get_ops_rules()

    def analyze(self, account_id: int | None = None) -> tuple[list[CampaignAnalysis], RefDates]:
        refs = resolve_ref_dates(self.db, account_id)
        meta = self.repo.campaign_meta(account_id)
        metrics = self.repo.campaign_metrics_by_day([refs.latest, refs.prior], account_id)
        qs = self.repo.avg_quality_score_by_campaign(refs.latest, account_id)
        disapproved = self.repo.disapproved_ads_by_campaign(account_id)

        results: list[CampaignAnalysis] = []
        for pk, m in meta.items():
            today_raw = metrics.get((pk, refs.latest), {})
            prior_raw = metrics.get((pk, refs.prior), {})
            today = DayMetrics(
                impressions=today_raw.get("impressions", 0),
                clicks=today_raw.get("clicks", 0),
                cost=today_raw.get("cost", 0.0),
                conversions=today_raw.get("conversions", 0.0),
            )
            prior = DayMetrics(
                impressions=prior_raw.get("impressions", 0),
                clicks=prior_raw.get("clicks", 0),
                cost=prior_raw.get("cost", 0.0),
                conversions=prior_raw.get("conversions", 0.0),
            )
            daily_budget = today_raw.get("budget", 0.0) or prior_raw.get("budget", 0.0)
            ctx = CampaignContext(
                status=m["status"] or "",
                daily_budget=daily_budget,
                spend_today=today.cost,
                optimization_score=m["optimization_score"],
                avg_quality_score=qs.get(pk),
                disapproved_ads=disapproved.get(pk, 0),
                today=today,
                prior=prior,
            )
            health = compute_campaign_health(ctx, self.rules.health)
            priority = compute_priority(health, today.cost, self.rules.priority)
            results.append(
                CampaignAnalysis(
                    campaign_pk=pk,
                    campaign_id=m["campaign_id"],
                    name=m["name"],
                    account_id=m["account_id"],
                    status=m["status"],
                    daily_budget=round(daily_budget, 2),
                    spend_today=round(today.cost, 2),
                    spend_yesterday=round(prior.cost, 2),
                    budget_utilization=ctx.budget_utilization,
                    optimization_score=m["optimization_score"],
                    today=today,
                    prior=prior,
                    health=health,
                    priority=priority,
                )
            )
        return results, refs
