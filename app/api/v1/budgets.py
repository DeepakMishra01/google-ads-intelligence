"""Budget endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.entities import BudgetRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=Page[BudgetRead], summary="List budgets")
def list_budgets(
    account_id: int | None = Query(None),
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[BudgetRead]:
    items, total = svc.list_budgets(account_id=account_id, limit=page.limit, offset=page.offset)
    return Page(
        items=[BudgetRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
