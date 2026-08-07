"""Account endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_page_params, get_query_service
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
    db: Session = Depends(get_db),
) -> Page[AccountRead]:
    # The dropdown uses with_campaigns=true so empty shell accounts don't clutter it.
    if with_campaigns:
        with_camps = select(Campaign.account_id).distinct().scalar_subquery()
        items = (
            db.execute(
                select(Account)
                .where(Account.id.in_(with_camps), Account.is_manager.isnot(True))
                .order_by(Account.descriptive_name.nulls_last(), Account.customer_id)
            )
            .scalars()
            .all()
        )
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


@router.get("/rollup", response_model=None, summary="Account-level metrics rollup")
def account_rollup(
    days: int = Query(365, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ops.account_rollup_service import AccountRollupService

    return AccountRollupService(db).rollup(days=days)


@router.get("/{account_id}", response_model=AccountRead, summary="Get one account")
def get_account(account_id: int, svc: QueryService = Depends(get_query_service)) -> AccountRead:
    account = svc.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountRead.model_validate(account)
