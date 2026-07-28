"""Campaign Explorer - search campaigns by name across accounts over any range."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import OpsFilters, get_campaign_search_service, get_ops_filters
from app.schemas.ops import CampaignSearchResponse
from app.services.ops.campaign_search_service import CampaignSearchService

router = APIRouter(prefix="/campaigns", tags=["command-center"])


@router.get(
    "/search",
    response_model=CampaignSearchResponse,
    summary="Search campaigns by name over a date range (with grand totals)",
)
def search_campaigns(
    filters: OpsFilters = Depends(get_ops_filters),
    q: str | None = Query(None, description="Campaign name contains (case-insensitive)."),
    limit: int = Query(500, ge=1, le=2000),
    svc: CampaignSearchService = Depends(get_campaign_search_service),
) -> CampaignSearchResponse:
    data = svc.search(
        q=q,
        account_id=filters.account_id,
        days=filters.days,
        start=filters.start,
        end=filters.end,
        limit=limit,
    )
    return CampaignSearchResponse(**data)
