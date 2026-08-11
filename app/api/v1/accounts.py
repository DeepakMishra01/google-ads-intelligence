"""Account endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    PageParams,
    get_current_user,
    get_page_params,
    get_query_service,
    require_admin,
    verify_account_access,
    verify_path_account_access,
)
from app.database.session import get_db
from app.models.account import Account
from app.models.campaign import Campaign
from app.schemas.common import Page
from app.schemas.entities import AccountRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=Page[AccountRead], summary="List accounts")
def list_accounts(
    page: PageParams = Depends(get_page_params),
    with_campaigns: bool = Query(False, description="Only accounts that have campaigns."),
    svc: QueryService = Depends(get_query_service),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[AccountRead]:
    # Managers only ever see the accounts assigned to them (the dropdown source).
    allowed = user.allowed_account_ids  # None => admin/all
    if with_campaigns or allowed is not None:
        with_camps = select(Campaign.account_id).distinct().scalar_subquery()
        stmt = (
            select(Account)
            .where(Account.is_manager.isnot(True))
            .order_by(Account.descriptive_name.nulls_last(), Account.customer_id)
        )
        if with_campaigns:
            stmt = stmt.where(Account.id.in_(with_camps))
        if allowed is not None:
            stmt = stmt.where(Account.id.in_(allowed))
        items = db.execute(stmt).scalars().all()
        return Page(
            items=[AccountRead.model_validate(i) for i in items],
            total=len(items),
            limit=len(items),
            offset=0,
        )
    items, total = svc.list_accounts(limit=page.limit, offset=page.offset)
    return Page(
        items=[AccountRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


def _parse_date(s: str | None):
    from datetime import date

    return date.fromisoformat(s) if s else None


@router.get("/rollup", response_model=None, summary="Account-level metrics rollup")
def account_rollup(
    days: int = Query(365, ge=1, le=3650),
    start: str | None = Query(None, description="YYYY-MM-DD (overrides days)."),
    end: str | None = Query(None),
    account_id: int | None = Query(None, description="Limit to one account."),
    user: CurrentUser = Depends(verify_account_access),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ops.account_rollup_service import AccountRollupService

    return AccountRollupService(db).rollup(
        days=days, start=_parse_date(start), end=_parse_date(end), account_id=account_id,
        allowed_account_ids=user.allowed_account_ids,
    )


@router.get("/rollup/export", response_model=None, summary="Account breakdown as Excel")
def account_rollup_export(
    days: int = Query(365, ge=1, le=3650),
    start: str | None = Query(None),
    end: str | None = Query(None),
    account_id: int | None = Query(None, description="Limit to one account."),
    user: CurrentUser = Depends(require_admin),  # downloads are admin-only
    db: Session = Depends(get_db),
):
    from fastapi.responses import StreamingResponse

    from app.services.ops.account_rollup_service import AccountRollupService

    s, e = _parse_date(start), _parse_date(end)
    data = AccountRollupService(db).export_bytes(
        days=days, start=s, end=e, account_id=account_id,
        allowed_account_ids=user.allowed_account_ids,
    )
    label = f"{s}_{e}" if s and e else f"last-{days}d"
    fname = f"account-breakdown_{label}.xlsx"
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/{account_id}/campaigns", response_model=None, summary="Account's campaign breakdown")
def account_campaigns(
    account_id: int,
    days: int = Query(365, ge=1, le=3650),
    start: str | None = Query(None),
    end: str | None = Query(None),
    _: CurrentUser = Depends(verify_path_account_access),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ops.account_rollup_service import AccountRollupService

    return AccountRollupService(db).campaigns(
        account_id, days=days, start=_parse_date(start), end=_parse_date(end)
    )


@router.get("/{account_id}", response_model=AccountRead, summary="Get one account")
def get_account(
    account_id: int,
    _: CurrentUser = Depends(verify_path_account_access),
    svc: QueryService = Depends(get_query_service),
) -> AccountRead:
    account = svc.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountRead.model_validate(account)
