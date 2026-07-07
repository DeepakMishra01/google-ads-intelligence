"""Campaign Health service (Module 2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops.campaign_analysis import CampaignAnalysis, CampaignAnalyzer

# Map the health band to an operator-facing priority label.
_LEVEL_TO_PRIORITY = {
    "healthy": "low",
    "warning": "medium",
    "high": "high",
    "critical": "critical",
    "ignored": "none",
}

_SORTS = {
    "priority": lambda a: -a.priority.score,
    "health": lambda a: a.health.score,
    "spend": lambda a: -a.spend_today,
    "budget": lambda a: -(a.budget_utilization or 0),
}


class CampaignHealthService:
    def __init__(self, db: Session) -> None:
        self.analyzer = CampaignAnalyzer(db)

    def _row(self, a: CampaignAnalysis) -> dict[str, Any]:
        return {
            "campaign_pk": a.campaign_pk,
            "campaign_id": a.campaign_id,
            "campaign_name": a.name,
            "account_id": a.account_id,
            "status": a.status,
            "health_score": a.health.score,
            "health_level": a.health.level,
            "priority_level": _LEVEL_TO_PRIORITY.get(a.health.level, "none"),
            "priority_score": a.priority.score,
            "daily_budget": a.daily_budget,
            "spend_today": a.spend_today,
            "spend_yesterday": a.spend_yesterday,
            "budget_utilization": (
                round(a.budget_utilization, 4) if a.budget_utilization is not None else None
            ),
            "optimization_score": a.optimization_score,
            "impressions": a.today.impressions,
            "clicks": a.today.clicks,
            "ctr": a.today.ctr,
            "avg_cpc": a.today.avg_cpc,
            "issues": a.health.issue_labels,
            "suggested_reason": a.health.primary_reason,
            "estimated_wasted_spend": a.priority.estimated_wasted_spend,
        }

    def health(
        self,
        *,
        account_id: int | None = None,
        sort: str = "priority",
        attention_only: bool = False,
        include_paused: bool = False,
    ) -> list[dict[str, Any]]:
        analyses, _ = self.analyzer.analyze(account_id)
        if not include_paused:
            analyses = [a for a in analyses if a.health.is_active]
        if attention_only:
            analyses = [a for a in analyses if a.health.level in ("warning", "high", "critical")]
        analyses.sort(key=_SORTS.get(sort, _SORTS["priority"]))
        return [self._row(a) for a in analyses]
