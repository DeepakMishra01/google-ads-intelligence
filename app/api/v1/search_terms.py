"""Search term endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageParams, get_page_params, get_query_service
from app.schemas.common import Page
from app.schemas.entities import SearchTermRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/searchterms", tags=["search_terms"])


@router.get("", response_model=Page[SearchTermRead], summary="List search terms")
def list_search_terms(
    account_id: int | None = Query(None),
    ad_group_id: int | None = Query(None, description="Filter by internal ad group id."),
    page: PageParams = Depends(get_page_params),
    svc: QueryService = Depends(get_query_service),
) -> Page[SearchTermRead]:
    items, total = svc.list_search_terms(
        account_id=account_id,
        ad_group_id=ad_group_id,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[SearchTermRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
