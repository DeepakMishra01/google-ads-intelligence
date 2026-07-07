"""Account endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.entities import AccountRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=Page[AccountRead], summary="List accounts")
def list_accounts(
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[AccountRead]:
    items, total = svc.list_accounts(limit=page.limit, offset=page.offset)
    return Page(
        items=[AccountRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{account_id}", response_model=AccountRead, summary="Get one account")
def get_account(account_id: int, svc: QueryService = Depends(get_query_service)) -> AccountRead:
    account = svc.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountRead.model_validate(account)
