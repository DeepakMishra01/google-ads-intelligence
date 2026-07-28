"""Dashboard-ready aggregate endpoints for the Ops team UI / future AI agents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_dashboard_service
from app.schemas.dashboard import (
    BudgetUtilizationRow,
    CampaignPerformanceRow,
    CampaignTrendPoint,
    DailySpendPoint,
    KeywordHealthRow,
    SearchTermRow,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Common query params reused across endpoints.
_Days = Query(30, ge=1, le=3650, description="Lookback window in days.")
_Account = Query(None, description="Filter by internal account id.")
_Limit = Query(20, ge=1, le=200)


@router.get("/top-spending-campaigns", response_model=list[CampaignPerformanceRow])
def top_spending_campaigns(
    account_id: int | None = _Account,
    days: int = _Days,
    limit: int = _Limit,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.top_spending_campaigns(account_id=account_id, days=days, limit=limit)


@router.get("/highest-cpc-campaigns", response_model=list[CampaignPerformanceRow])
def highest_cpc_campaigns(
    account_id: int | None = _Account,
    days: int = _Days,
    limit: int = _Limit,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.highest_cpc_campaigns(account_id=account_id, days=days, limit=limit)


@router.get("/lowest-ctr-campaigns", response_model=list[CampaignPerformanceRow])
def lowest_ctr_campaigns(
    account_id: int | None = _Account,
    days: int = _Days,
    limit: int = _Limit,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.lowest_ctr_campaigns(account_id=account_id, days=days, limit=limit)


@router.get("/campaign-health", response_model=list[CampaignPerformanceRow])
def campaign_health(
    account_id: int | None = _Account,
    days: int = _Days,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.campaign_health(account_id=account_id, days=days)


@router.get("/keyword-health", response_model=list[KeywordHealthRow])
def keyword_health(
    account_id: int | None = _Account,
    days: int = _Days,
    limit: int = Query(50, ge=1, le=500),
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[KeywordHealthRow]:
    return svc.keyword_health(account_id=account_id, days=days, limit=limit)


@router.get("/search-term-report", response_model=list[SearchTermRow])
def search_term_report(
    account_id: int | None = _Account,
    days: int = _Days,
    limit: int = Query(50, ge=1, le=500),
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[SearchTermRow]:
    return svc.search_term_report(account_id=account_id, days=days, limit=limit)


@router.get("/budget-utilization", response_model=list[BudgetUtilizationRow])
def budget_utilization(
    account_id: int | None = _Account,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[BudgetUtilizationRow]:
    return svc.budget_utilization(account_id=account_id)


@router.get("/daily-spend-trend", response_model=list[DailySpendPoint])
def daily_spend_trend(
    account_id: int | None = _Account,
    days: int = _Days,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[DailySpendPoint]:
    return svc.daily_spend_trend(account_id=account_id, days=days)


@router.get("/campaign-trend/{campaign_id}", response_model=list[CampaignTrendPoint])
def campaign_trend(
    campaign_id: int,
    days: int = _Days,
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignTrendPoint]:
    return svc.campaign_trend(campaign_pk=campaign_id, days=days)
