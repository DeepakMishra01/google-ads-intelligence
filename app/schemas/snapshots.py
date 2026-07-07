"""Read schemas for append-only snapshot (time-series) rows."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.common import ORMModel


class _MetricsRead(ORMModel):
    impressions: int
    clicks: int
    interactions: int
    cost_micros: int
    ctr: float | None
    average_cpc_micros: int | None
    average_cpm_micros: int | None
    conversions: float
    conversions_value: float
    all_conversions: float
    video_views: int


class CampaignSnapshotRead(_MetricsRead):
    id: int
    account_id: int
    campaign_id: int
    snapshot_date: date
    sync_time: datetime
    status: str | None
    budget_micros: int | None
    bidding_strategy_type: str | None
    optimization_score: float | None


class AdGroupSnapshotRead(_MetricsRead):
    id: int
    account_id: int
    ad_group_id: int
    campaign_id: int
    snapshot_date: date
    sync_time: datetime
    status: str | None
    cpc_bid_micros: int | None


class KeywordSnapshotRead(_MetricsRead):
    id: int
    account_id: int
    keyword_id: int
    ad_group_id: int
    campaign_id: int
    snapshot_date: date
    sync_time: datetime
    match_type: str | None
    status: str | None
    quality_score: int | None
    expected_ctr: str | None
    landing_page_experience: str | None
    ad_relevance: str | None


class AdSnapshotRead(_MetricsRead):
    id: int
    account_id: int
    ad_id: int
    ad_group_id: int
    campaign_id: int
    snapshot_date: date
    sync_time: datetime
    status: str | None
    approval_status: str | None


class SearchTermSnapshotRead(_MetricsRead):
    id: int
    account_id: int
    search_term_id: int
    campaign_id: int
    ad_group_id: int
    snapshot_date: date
    sync_time: datetime
