"""Repository for AI Ad Copy generation history."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.ad_copy import AdCopyGeneration
from app.repositories.base import BaseRepository


class AdCopyRepository(BaseRepository[AdCopyGeneration]):
    model = AdCopyGeneration

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def record(self, values: dict[str, Any]) -> AdCopyGeneration:
        """Persist one generation run and return the stored row."""
        return self.add(AdCopyGeneration(**values))

    def recent(
        self, *, campus: str | None = None, limit: int = 50
    ) -> list[AdCopyGeneration]:
        stmt = select(AdCopyGeneration)
        if campus:
            stmt = stmt.where(AdCopyGeneration.campus.ilike(f"%{campus}%"))
        stmt = stmt.order_by(desc(AdCopyGeneration.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
