"""Module 3 - Alerts endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    PageParams,
    get_alerts_service,
    get_page_params,
    require_api_key,
    require_role,
)
from app.schemas.common import Page
from app.schemas.ops import (
    AlertEvaluateResult,
    AlertRead,
    AlertStatusUpdate,
    AlertSummary,
)
from app.services.ops.alerts_service import AlertsService

router = APIRouter(prefix="/alerts", tags=["command-center"])


@router.get("", response_model=Page[AlertRead], summary="List alerts")
def list_alerts(
    page: PageParams = Depends(get_page_params),
    status: str | None = Query(None, pattern="^(open|resolved|dismissed)$"),
    severity: str | None = Query(None, pattern="^(critical|high|medium|low)$"),
    account_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    alert_type: str | None = Query(None),
    svc: AlertsService = Depends(get_alerts_service),
) -> Page[AlertRead]:
    items, total = svc.list_alerts(
        status=status,
        severity=severity,
        account_id=account_id,
        entity_type=entity_type,
        alert_type=alert_type,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[AlertRead.model_validate(a) for a in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/summary", response_model=AlertSummary, summary="Open alert counts")
def alert_summary(
    account_id: int | None = Query(None),
    svc: AlertsService = Depends(get_alerts_service),
) -> AlertSummary:
    return AlertSummary(**svc.summary(account_id=account_id))


@router.post(
    "/evaluate",
    response_model=AlertEvaluateResult,
    summary="Run the alert engine",
    dependencies=[Depends(require_role("manager")), Depends(require_api_key)],
)
def evaluate(
    account_id: int | None = Query(None),
    svc: AlertsService = Depends(get_alerts_service),
) -> AlertEvaluateResult:
    return AlertEvaluateResult(**svc.evaluate(account_id=account_id))


@router.patch(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Update alert status",
    dependencies=[Depends(require_role("manager"))],
)
def update_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    svc: AlertsService = Depends(get_alerts_service),
) -> AlertRead:
    alert = svc.set_status(alert_id, payload.status)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertRead.model_validate(alert)
