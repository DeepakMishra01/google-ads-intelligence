"""Module 4 - Search Term Explorer endpoint (rich filtering + pagination)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageParams, get_page_params, get_search_explorer_service
from app.schemas.common import Page
from app.schemas.ops import SearchTermRow
from app.services.ops.search_explorer_service import SearchExplorerService

router = APIRouter(prefix="/searchterms", tags=["command-center"])


@router.get("/explore", response_model=Page[SearchTermRow], summary="Explore search terms")
def explore(
    page: PageParams = Depends(get_page_params),
    account_id: int | None = Query(None),
    campaign_id: int | None = Query(None, description="Internal campaign id."),
    ad_group_id: int | None = Query(None, description="Internal ad group id."),
    days: int = Query(30, ge=1, le=3650),
    min_clicks: int = Query(0, ge=0),
    min_cost: float = Query(0.0, ge=0),
    min_ctr: float | None = Query(None, ge=0, le=1, description="Minimum CTR (0-1)."),
    contains: str | None = Query(None, description="Case-insensitive substring match."),
    sort: str = Query("cost", pattern="^(cost|clicks|impressions|conversions)$"),
    svc: SearchExplorerService = Depends(get_search_explorer_service),
) -> Page[SearchTermRow]:
    items, total = svc.explore(
        account_id=account_id,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        days=days,
        min_clicks=min_clicks,
        min_cost=min_cost,
        min_ctr=min_ctr,
        contains=contains,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[SearchTermRow(**i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
