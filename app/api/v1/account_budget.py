"""Account-level budget endpoints: view (scoped) + admin set (monthly / total)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.api.deps import CurrentUser, get_current_user
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


@router.put("", response_model=None, summary="Set an account budget")
def set_account_budget(
    body: SetAccountBudget,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # Overall (total) account budget is the admin's allocation → admin only.
    # Monthly budgets are the AM's own plan → any user with access to the account.
    if body.period == "total":
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Only admins set the overall account budget.")
    elif not user.is_admin:
        if user.allowed_account_ids is None or body.account_id not in user.allowed_account_ids:
            raise HTTPException(status_code=403, detail="You can only set budgets for your accounts.")
    return AccountBudgetService(db).set_budget(
        account_id=body.account_id, period=body.period, amount=body.amount,
        period_start=body.period_start, by=user.email,
    )
