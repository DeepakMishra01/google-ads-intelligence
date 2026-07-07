"""Module 6 - Budget Monitoring endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_budget_service
from app.schemas.ops import BudgetMonitorRow
from app.services.ops.budget_service import BudgetService

router = APIRouter(prefix="/budgets", tags=["command-center"])


@router.get("/monitoring", response_model=list[BudgetMonitorRow], summary="Budget risk monitor")
def budget_monitoring(
    account_id: int | None = Query(None, description="Filter by internal account id."),
    svc: BudgetService = Depends(get_budget_service),
) -> list[BudgetMonitorRow]:
    return [BudgetMonitorRow(**r) for r in svc.monitoring(account_id=account_id)]
