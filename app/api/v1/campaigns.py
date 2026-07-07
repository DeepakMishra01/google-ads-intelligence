"""Campaign endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.entities import CampaignRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=Page[CampaignRead], summary="List campaigns")
def list_campaigns(
    account_id: int | None = Query(None, description="Filter by internal account id."),
    status: str | None = Query(None, description="Filter by campaign status."),
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[CampaignRead]:
    items, total = svc.list_campaigns(
        account_id=account_id, status=status, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[CampaignRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{campaign_id}", response_model=CampaignRead, summary="Get one campaign")
def get_campaign(campaign_id: int, svc: QueryService = Depends(get_query_service)) -> CampaignRead:
    campaign = svc.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)
