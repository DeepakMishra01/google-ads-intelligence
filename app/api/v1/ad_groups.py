"""Ad group endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.entities import AdGroupRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/adgroups", tags=["ad_groups"])


@router.get("", response_model=Page[AdGroupRead], summary="List ad groups")
def list_ad_groups(
    account_id: int | None = Query(None),
    campaign_id: int | None = Query(None, description="Filter by internal campaign id."),
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[AdGroupRead]:
    items, total = svc.list_ad_groups(
        account_id=account_id,
        campaign_id=campaign_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[AdGroupRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
