"""Module 1 - Executive Overview endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_overview_service
from app.schemas.ops import OverviewResponse
from app.services.ops.overview_service import OverviewService

router = APIRouter(prefix="/dashboard", tags=["command-center"])


@router.get("/overview", response_model=OverviewResponse, summary="Executive overview")
def overview(
    account_id: int | None = Query(None, description="Filter by internal account id."),
    svc: OverviewService = Depends(get_overview_service),
) -> OverviewResponse:
    return OverviewResponse(**svc.overview(account_id=account_id))
