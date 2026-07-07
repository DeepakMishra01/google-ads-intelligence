"""Module 8 - Priority Engine endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_priority_service
from app.schemas.ops import PriorityTask
from app.services.ops.priority_service import PriorityService

router = APIRouter(prefix="/priorities", tags=["command-center"])


@router.get("", response_model=list[PriorityTask], summary="Prioritized task list")
def priorities(
    account_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    svc: PriorityService = Depends(get_priority_service),
) -> list[PriorityTask]:
    return [PriorityTask(**t) for t in svc.priorities(account_id=account_id, limit=limit)]
