"""Audit log repository."""

from __future__ import annotations

from sqlalchemy import desc, select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def record(self, **values: object) -> AuditLog:
        entry = AuditLog(**values)
        self.db.add(entry)
        self.db.flush()
        return entry

    def recent(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
