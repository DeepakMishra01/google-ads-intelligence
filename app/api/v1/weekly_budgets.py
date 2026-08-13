"""Weekly budget endpoints: view (scoped) + admin set + admin email trigger."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_admin
from app.database.session import get_db
from app.services.ops.weekly_budget_service import WeeklyBudgetService

router = APIRouter(prefix="/weekly-budgets", tags=["budgets"])


class SetWeeklyBudget(BaseModel):
    account_id: int
    week_start: date  # any day in the week; snapped to Monday
    amount: float


@router.get("", response_model=None, summary="Weekly budget vs spend (scoped)")
def weekly_overview(
    weeks: int = Query(8, ge=1, le=26),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return WeeklyBudgetService(db).overview(
        allowed_account_ids=user.allowed_account_ids, weeks=weeks
    )


@router.put("", response_model=None, summary="Set an account's weekly budget (admin)")
def set_weekly_budget(
    body: SetWeeklyBudget,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return WeeklyBudgetService(db).set_budget(
        account_id=body.account_id, week_start=body.week_start,
        amount=body.amount, by=admin.email,
    )


@router.post("/email", response_model=None, summary="Send the weekly summary to admins now (admin)")
def send_weekly_email(
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ops.weekly_budget_tasks import send_weekly_budget_email

    return send_weekly_budget_email(db)
