"""Account-level budget endpoints: view (scoped) + admin set (monthly / total)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_admin
from app.database.session import get_db
from app.services.ops.account_budget_service import AccountBudgetService

router = APIRouter(prefix="/account-budget", tags=["budgets"])


class SetAccountBudget(BaseModel):
    account_id: int
    period: str  # 'month' | 'total'
    amount: float
    period_start: date | None = None  # any day in the month (month period only)


@router.get("/overview", response_model=None, summary="Account budgets: monthly + all-time (scoped)")
def account_budget_overview(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return AccountBudgetService(db).overview(allowed_account_ids=user.allowed_account_ids)


@router.put("", response_model=None, summary="Set an account budget (admin)")
def set_account_budget(
    body: SetAccountBudget,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return AccountBudgetService(db).set_budget(
        account_id=body.account_id, period=body.period, amount=body.amount,
        period_start=body.period_start, by=admin.email,
    )
