"""Module 2 - Campaign Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import OpsFilters, get_campaign_health_service, get_ops_filters
from app.schemas.ops import CampaignHealthRow
from app.services.ops.health_service import CampaignHealthService

router = APIRouter(prefix="/campaigns", tags=["command-center"])


@router.get("/health", response_model=list[CampaignHealthRow], summary="Campaign health scores")
def campaign_health(
    filters: OpsFilters = Depends(get_ops_filters),
    sort: str = Query("priority", pattern="^(priority|health|spend|budget)$"),
    attention_only: bool = Query(False, description="Only warning/high/critical campaigns."),
    include_paused: bool = Query(False, description="Include paused/removed campaigns."),
    svc: CampaignHealthService = Depends(get_campaign_health_service),
) -> list[CampaignHealthRow]:
    rows = svc.health(
        account_id=filters.account_id,
        sort=sort,
        attention_only=attention_only,
        include_paused=include_paused,
    )
    return [CampaignHealthRow(**r) for r in rows]
