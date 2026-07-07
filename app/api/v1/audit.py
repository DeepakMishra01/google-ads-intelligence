"""Module 13 - Audit log endpoint (admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PageParams, get_page_params, require_role
from app.database.session import get_db
from app.repositories.audit_log import AuditLogRepository
from app.schemas.ops import AuditLogRead

router = APIRouter(prefix="/audit", tags=["command-center"])


@router.get(
    "/logs",
    response_model=list[AuditLogRead],
    summary="Recent audit log entries",
    dependencies=[Depends(require_role("admin"))],
)
def audit_logs(
    page: PageParams = Depends(get_page_params),
    db: Session = Depends(get_db),
) -> list[AuditLogRead]:
    repo = AuditLogRepository(db)
    return [
        AuditLogRead.model_validate(x)
        for x in repo.recent(limit=page.limit, offset=page.offset)
    ]
