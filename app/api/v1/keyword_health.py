"""Module 5 - Keyword Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import OpsFilters, get_keyword_health_service, get_ops_filters
from app.schemas.ops import KeywordHealthRow
from app.services.ops.keyword_service import KeywordHealthService

router = APIRouter(prefix="/keywords", tags=["command-center"])

_SORTS = "^(worst|highest_spend|lowest_ctr|highest_cpc|lowest_quality_score)$"


@router.get("/health", response_model=list[KeywordHealthRow], summary="Keyword health scores")
def keyword_health(
    filters: OpsFilters = Depends(get_ops_filters),
    campaign_id: int | None = Query(None, description="Internal campaign id."),
    sort: str = Query("worst", pattern=_SORTS),
    limit: int = Query(50, ge=1, le=500),
    svc: KeywordHealthService = Depends(get_keyword_health_service),
) -> list[KeywordHealthRow]:
    rows = svc.health(
        account_id=filters.account_id,
        campaign_id=campaign_id,
        days=filters.days,
        sort=sort,
        limit=limit,
    )
    return [KeywordHealthRow(**r) for r in rows]
