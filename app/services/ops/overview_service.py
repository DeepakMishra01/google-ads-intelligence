"""Executive Overview service (Module 1).

Answers "what's the state of everything right now?" in a single call. All figures
are for the latest fully-synced day (operationally "yesterday").
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config.ops_rules import get_ops_rules
from app.repositories.ops import OpsRepository
from app.repositories.sync_log import SyncLogRepository
from app.services.ops.dates import resolve_ref_dates
from app.utils.cache import dashboard_cache


class OverviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ops = OpsRepository(db)
        self.sync_logs = SyncLogRepository(db)
        self.rules = get_ops_rules()

    def overview(self, *, account_id: int | None = None, use_cache: bool = True) -> dict[str, Any]:
        if not use_cache:
            return self._build(account_id)
        return dashboard_cache.get_or_set(
            f"overview:{account_id}", lambda: self._build(account_id), ttl=45
        )

    def _build(self, account_id: int | None) -> dict[str, Any]:
        refs = resolve_ref_dates(self.db, account_id)
        counts = self.ops.entity_counts(account_id)
        totals = self.ops.account_day_totals(refs.latest, account_id)
        disapproved_ads = sum(self.ops.disapproved_ads_by_campaign(account_id).values())

        clicks = totals["clicks"]
        impressions = totals["impressions"]
        cost = totals["cost"]
        avg_ctr = (clicks / impressions) if impressions else None
        avg_cpc = (cost / clicks) if clicks else None

        latest_sync = self.sync_logs.latest()
        last_ok = self.sync_logs.last_successful()

        return {
            "reference_date": refs.latest,
            "total_accounts": counts["accounts"],
            "total_active_campaigns": counts["campaigns_active"],
            "total_active_ad_groups": counts["ad_groups_active"],
            "total_active_keywords": counts["keywords_active"],
            "yesterday_spend": cost,
            "yesterday_clicks": clicks,
            "yesterday_impressions": impressions,
            "average_ctr": avg_ctr,
            "average_cpc": avg_cpc,
            "campaigns_limited_by_budget": self.ops.campaigns_limited_by_budget_count(
                refs.latest, account_id
            ),
            "disapproved_ads": disapproved_ads,
            # Keyword policy approval is not captured by the Phase 1 sync; exposed
            # as 0 until that field is added to the keyword snapshot.
            "disapproved_keywords": 0,
            "low_quality_score_keywords": self.ops.low_quality_keyword_count(
                refs.latest, self.rules.health.quality_score_floor, account_id
            ),
            "new_search_terms_since_yesterday": self.ops.new_search_terms_count(
                refs.latest, account_id
            ),
            # Headline the last *successful* sync — a few permanently-inaccessible
            # accounts (cancelled/suspended) shouldn't read as a global failure.
            "sync_status": (
                last_ok.status if last_ok else (latest_sync.status if latest_sync else "never")
            ),
            "last_successful_sync": last_ok.finished_at if last_ok else None,
        }
