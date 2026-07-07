"""Dashboard-optimized response schemas (currency amounts already converted)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CampaignPerformanceRow(BaseModel):
    campaign_pk: int
    campaign_id: int
    campaign_name: str | None
    account_id: int
    status: str | None
    optimization_score: float | None
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None
    cost_per_conversion: float | None


class KeywordHealthRow(BaseModel):
    keyword_pk: int
    text: str | None
    match_type: str | None
    account_id: int
    avg_quality_score: float | None
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None


class SearchTermRow(BaseModel):
    search_term_pk: int
    query: str
    account_id: int
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None


class BudgetUtilizationRow(BaseModel):
    budget_pk: int
    name: str | None
    account_id: int
    snapshot_date: date | None
    amount: float
    spend: float
    utilization: float | None


class DailySpendPoint(BaseModel):
    date: date
    cost: float
    clicks: int
    impressions: int
    conversions: float


class CampaignTrendPoint(BaseModel):
    date: date
    impressions: int
    clicks: int
    cost: float
    conversions: float
    ctr: float | None
    avg_cpc: float | None
