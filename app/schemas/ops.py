"""Response/request schemas for the Operations Command Center (Phase 2)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.common import ORMModel


# --------------------------------------------------------------------------- #
# Module 1 - Executive Overview
# --------------------------------------------------------------------------- #
class OverviewResponse(BaseModel):
    reference_date: date
    total_accounts: int
    total_active_campaigns: int
    total_active_ad_groups: int
    total_active_keywords: int
    yesterday_spend: float
    yesterday_clicks: int
    yesterday_impressions: int
    average_ctr: float | None
    average_cpc: float | None
    campaigns_limited_by_budget: int
    disapproved_ads: int
    disapproved_keywords: int
    low_quality_score_keywords: int
    new_search_terms_since_yesterday: int
    sync_status: str
    last_successful_sync: datetime | None


# --------------------------------------------------------------------------- #
# Module 2 - Campaign Health
# --------------------------------------------------------------------------- #
class CampaignHealthRow(BaseModel):
    campaign_pk: int
    campaign_id: int
    campaign_name: str | None
    account_id: int
    status: str | None
    health_score: int
    health_level: str
    priority_level: str
    priority_score: int
    daily_budget: float
    spend_today: float
    spend_yesterday: float
    budget_utilization: float | None
    optimization_score: float | None
    impressions: int
    clicks: int
    ctr: float | None
    avg_cpc: float | None
    issues: list[str]
    suggested_reason: str | None
    estimated_wasted_spend: float


# --------------------------------------------------------------------------- #
# Module 5 - Keyword Health
# --------------------------------------------------------------------------- #
class KeywordHealthRow(BaseModel):
    keyword_pk: int
    text: str | None
    match_type: str | None
    account_id: int
    campaign_id: int | None
    quality_score: int | None
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None
    health_score: int
    health_level: str
    issues: list[str]
    recommendation: str | None


# --------------------------------------------------------------------------- #
# Module 6 - Budget Monitoring
# --------------------------------------------------------------------------- #
class BudgetMonitorRow(BaseModel):
    budget_pk: int
    name: str | None
    account_id: int
    snapshot_date: date | None
    budget: float
    current_spend: float
    remaining_budget: float
    utilization: float | None
    projected_eod_spend: float
    risk: str


# --------------------------------------------------------------------------- #
# Module 4 - Search Term Explorer
# --------------------------------------------------------------------------- #
class SearchTermRow(BaseModel):
    search_term_pk: int
    query: str
    status: str | None
    campaign_name: str | None
    ad_group_name: str | None
    clicks: int
    impressions: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None


# --------------------------------------------------------------------------- #
# Module 7 - Trend Analytics
# --------------------------------------------------------------------------- #
class TrendPoint(BaseModel):
    date: date
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None


class GrowthPoint(BaseModel):
    date: date
    campaigns: int
    keywords: int
    search_terms: int


class DayComparison(BaseModel):
    latest_date: date
    prior_date: date
    latest: dict[str, Any]
    prior: dict[str, Any]
    deltas: dict[str, float]


# --------------------------------------------------------------------------- #
# Module 8 - Priority Engine
# --------------------------------------------------------------------------- #
class PriorityTask(BaseModel):
    campaign_pk: int
    campaign_id: int
    campaign_name: str | None
    account_id: int
    priority_score: int
    health_score: int
    reasons: list[str]
    estimated_review_minutes: int
    estimated_wasted_spend: float
    spend_today: float


# --------------------------------------------------------------------------- #
# Module 3 - Alerts
# --------------------------------------------------------------------------- #
class AlertRead(ORMModel):
    id: int
    account_id: int | None
    entity_type: str
    entity_id: int | None
    entity_name: str | None
    alert_type: str
    severity: str
    status: str
    title: str
    description: str | None
    suggested_action: str | None
    metric_value: float | None
    threshold_value: float | None
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None


class AlertSummary(BaseModel):
    open_total: int
    by_severity: dict[str, int]


class AlertEvaluateResult(BaseModel):
    evaluated_campaigns: int
    reference_date: date
    alerts_active: int
    created: int
    auto_resolved: int


class AlertStatusUpdate(BaseModel):
    status: Literal["open", "resolved", "dismissed"]


# --------------------------------------------------------------------------- #
# Module 10 - Reporting
# --------------------------------------------------------------------------- #
class ReportResponse(BaseModel):
    period: str
    start_date: date
    end_date: date
    account_id: int | None
    totals: dict[str, Any]
    campaign_count: int
    campaigns: list[dict[str, Any]]
    alerts: AlertSummary


# --------------------------------------------------------------------------- #
# Module 13 - Audit
# --------------------------------------------------------------------------- #
class AuditLogRead(ORMModel):
    id: int
    actor: str | None
    role: str | None
    method: str
    path: str
    status_code: int | None
    duration_ms: int | None
    client_ip: str | None
    created_at: datetime
