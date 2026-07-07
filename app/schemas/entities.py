"""Read schemas for dimension entities (current-state resources).

Monetary ``*_micros`` fields are the raw API values; divide by 1,000,000 to get
the amount in the account currency.
"""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.common import ORMModel


class AccountRead(ORMModel):
    id: int
    customer_id: str
    descriptive_name: str | None
    currency_code: str | None
    time_zone: str | None
    status: str | None
    is_manager: bool
    manager_customer_id: str | None
    is_syncable: bool
    created_at: datetime
    updated_at: datetime


class CampaignRead(ORMModel):
    id: int
    account_id: int
    campaign_id: int
    name: str | None
    status: str | None
    serving_status: str | None
    advertising_channel_type: str | None
    advertising_channel_sub_type: str | None
    bidding_strategy_type: str | None
    networks: str | None
    start_date: date | None
    end_date: date | None
    optimization_score: float | None
    budget_id: int | None
    updated_at: datetime


class AdGroupRead(ORMModel):
    id: int
    account_id: int
    campaign_id: int
    ad_group_id: int
    name: str | None
    status: str | None
    type: str | None
    cpc_bid_micros: int | None
    updated_at: datetime


class KeywordRead(ORMModel):
    id: int
    account_id: int
    ad_group_id: int
    criterion_id: int
    text: str | None
    match_type: str | None
    status: str | None
    cpc_bid_micros: int | None
    updated_at: datetime


class AdRead(ORMModel):
    id: int
    account_id: int
    ad_group_id: int
    ad_id: int
    type: str | None
    status: str | None
    approval_status: str | None
    final_urls: str | None
    headlines: str | None
    descriptions: str | None
    updated_at: datetime


class SearchTermRead(ORMModel):
    id: int
    account_id: int
    campaign_id: int
    ad_group_id: int
    query: str
    match_type: str | None
    search_term_targeting_status: str | None
    updated_at: datetime


class BudgetRead(ORMModel):
    id: int
    account_id: int
    budget_id: int
    name: str | None
    amount_micros: int | None
    delivery_method: str | None
    period: str | None
    explicitly_shared: bool | None
    updated_at: datetime
