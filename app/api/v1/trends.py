"""Module 7 - Trend Analytics endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import OpsFilters, get_ops_filters, get_trend_service
from app.schemas.ops import DayComparison, GrowthPoint, TrendPoint
from app.services.ops.trend_service import TrendService

router = APIRouter(prefix="/trends", tags=["command-center"])


@router.get("/metrics", response_model=list[TrendPoint], summary="Daily metric trend")
def metric_trend(
    filters: OpsFilters = Depends(get_ops_filters),
    start: date | None = Query(None, description="Custom range start (overrides days)."),
    end: date | None = Query(None, description="Custom range end (overrides days)."),
    svc: TrendService = Depends(get_trend_service),
) -> list[TrendPoint]:
    rows = svc.metric_series(
        account_id=filters.account_id, days=filters.days, start=start, end=end
    )
    return [TrendPoint(**r) for r in rows]


@router.get("/growth", response_model=list[GrowthPoint], summary="Entity growth trend")
def growth_trend(
    filters: OpsFilters = Depends(get_ops_filters),
    start: date | None = Query(None),
    end: date | None = Query(None),
    svc: TrendService = Depends(get_trend_service),
) -> list[GrowthPoint]:
    rows = svc.growth_series(
        account_id=filters.account_id, days=filters.days, start=start, end=end
    )
    return [GrowthPoint(**r) for r in rows]


@router.get("/compare", response_model=DayComparison, summary="Today vs yesterday")
def compare(
    account_id: int | None = Query(None),
    svc: TrendService = Depends(get_trend_service),
) -> DayComparison:
    return DayComparison(**svc.compare_days(account_id=account_id))
