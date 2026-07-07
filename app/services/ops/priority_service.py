"""Priority Engine service (Module 8) - the prioritized task list.

Answers "where should I spend my next hour?" by ranking active campaigns on a
blended score of how unhealthy they are and how much money is at stake.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops.campaign_analysis import CampaignAnalyzer


class PriorityService:
    def __init__(self, db: Session) -> None:
        self.analyzer = CampaignAnalyzer(db)

    def priorities(
        self, *, account_id: int | None = None, limit: int = 20, min_score: int = 1
    ) -> list[dict[str, Any]]:
        analyses, _ = self.analyzer.analyze(account_id)
        tasks: list[dict[str, Any]] = []
        for a in analyses:
            if not a.health.is_active or a.priority.score < min_score:
                continue
            tasks.append(
                {
                    "campaign_pk": a.campaign_pk,
                    "campaign_id": a.campaign_id,
                    "campaign_name": a.name,
                    "account_id": a.account_id,
                    "priority_score": a.priority.score,
                    "health_score": a.health.score,
                    "reasons": a.priority.reasons,
                    "estimated_review_minutes": a.priority.estimated_review_minutes,
                    "estimated_wasted_spend": a.priority.estimated_wasted_spend,
                    "spend_today": a.spend_today,
                }
            )
        tasks.sort(key=lambda t: t["priority_score"], reverse=True)
        return tasks[:limit]
