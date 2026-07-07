"""Module 9 - Dashboard APIs (spec-named, speed-optimized aliases).

These endpoints expose the exact paths the Command Center UI expects, delegating
to the existing dashboard/ops services. Read-heavy ones are backed by the shared
TTL cache so repeated hits stay well under the latency budget.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_alerts_service,
    get_dashboard_service,
    get_keyword_health_service,
    get_priority_service,
    get_trend_service,
)
from app.schemas.dashboard import CampaignPerformanceRow, DailySpendPoint
from app.schemas.ops import AlertRead, GrowthPoint, KeywordHealthRow, PriorityTask
from app.services.dashboard_service import DashboardService
from app.services.ops.alerts_service import AlertsService
from app.services.ops.keyword_service import KeywordHealthService
from app.services.ops.priority_service import PriorityService
from app.services.ops.trend_service import TrendService
from app.utils.cache import dashboard_cache

router = APIRouter(prefix="/dashboard", tags=["command-center"])

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@router.get("/top-spenders", response_model=list[CampaignPerformanceRow])
def top_spenders(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    key = f"top-spenders:{account_id}:{days}:{limit}"
    return dashboard_cache.get_or_set(
        key, lambda: svc.top_spending_campaigns(account_id=account_id, days=days, limit=limit)
    )


@router.get("/highest-cpc", response_model=list[CampaignPerformanceRow])
def highest_cpc(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.highest_cpc_campaigns(account_id=account_id, days=days, limit=limit)


@router.get("/lowest-ctr", response_model=list[CampaignPerformanceRow])
def lowest_ctr(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    svc: DashboardService = Depends(get_dashboard_service),
) -> list[CampaignPerformanceRow]:
    return svc.lowest_ctr_campaigns(account_id=account_id, days=days, limit=limit)


@router.get("/quality-score", response_model=list[KeywordHealthRow])
def quality_score(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    svc: KeywordHealthService = Depends(get_keyword_health_service),
) -> list[KeywordHealthRow]:
    rows = svc.health(
        account_id=account_id, days=days, sort="lowest_quality_score", limit=limit
    )
    return [KeywordHealthRow(**r) for r in rows]


@router.get("/spend-trend", response_model=list[DailySpendPoint])
def spend_trend(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    svc: TrendService = Depends(get_trend_service),
) -> list[DailySpendPoint]:
    return [
        DailySpendPoint(
            date=r["date"],
            cost=r["cost"],
            clicks=r["clicks"],
            impressions=r["impressions"],
            conversions=r["conversions"],
        )
        for r in svc.metric_series(account_id=account_id, days=days)
    ]


@router.get("/searchterm-trend", response_model=list[GrowthPoint])
def searchterm_trend(
    account_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    svc: TrendService = Depends(get_trend_service),
) -> list[GrowthPoint]:
    return [GrowthPoint(**r) for r in svc.growth_series(account_id=account_id, days=days)]


@router.get("/alerts", response_model=list[AlertRead], summary="Open alerts, most severe first")
def dashboard_alerts(
    account_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    svc: AlertsService = Depends(get_alerts_service),
) -> list[AlertRead]:
    items, _ = svc.list_alerts(status="open", account_id=account_id, limit=limit)
    items.sort(key=lambda a: (_SEVERITY_RANK.get(a.severity, 9), a.last_seen_at), reverse=False)
    return [AlertRead.model_validate(a) for a in items]


@router.get("/priorities", response_model=list[PriorityTask])
def dashboard_priorities(
    account_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    svc: PriorityService = Depends(get_priority_service),
) -> list[PriorityTask]:
    return [PriorityTask(**t) for t in svc.priorities(account_id=account_id, limit=limit)]
