"""Sync log repository - reads/writes execution records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from app.models.sync_log import SyncLog
from app.repositories.base import BaseRepository


class SyncLogRepository(BaseRepository[SyncLog]):
    model = SyncLog

    def create_run(
        self,
        *,
        sync_type: str,
        entity: str,
        customer_id: str | None,
        started_at: datetime,
        attempt: int = 1,
        details: dict | None = None,
    ) -> SyncLog:
        run = SyncLog(
            sync_type=sync_type,
            entity=entity,
            customer_id=customer_id,
            started_at=started_at,
            attempt=attempt,
            status="running",
            details=details,
        )
        return self.add(run)

    def recent(self, *, limit: int = 50, customer_id: str | None = None) -> list[SyncLog]:
        stmt = select(SyncLog).order_by(desc(SyncLog.started_at)).limit(limit)
        if customer_id:
            stmt = stmt.where(SyncLog.customer_id == customer_id)
        return list(self.db.execute(stmt).scalars().all())

    def latest(self) -> SyncLog | None:
        stmt = select(SyncLog).order_by(desc(SyncLog.started_at)).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()
