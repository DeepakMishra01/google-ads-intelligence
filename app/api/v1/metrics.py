"""Metrics endpoints - raw campaign snapshot time-series."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.snapshots import CampaignSnapshotRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "",
    response_model=Page[CampaignSnapshotRead],
    summary="Campaign metric snapshots (time-series)",
)
def list_campaign_metrics(
    campaign_id: int | None = Query(None, description="Internal campaign id."),
    account_id: int | None = Query(None, description="Internal account id."),
    start: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)."),
    end: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)."),
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[CampaignSnapshotRead]:
    items, total = svc.list_campaign_metrics(
        campaign_id=campaign_id,
        account_id=account_id,
        start=start,
        end=end,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[CampaignSnapshotRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
