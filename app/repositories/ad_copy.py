"""Repository for AI Ad Copy generation history."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.ad_copy import AdCopyGeneration, ScorecardSnapshot
from app.repositories.base import BaseRepository


class ScorecardSnapshotRepository(BaseRepository[ScorecardSnapshot]):
    model = ScorecardSnapshot

    def save(self, values: dict[str, Any]) -> ScorecardSnapshot:
        row = ScorecardSnapshot(**values)
        self.db.add(row)
        self.db.flush()
        return row

    def history(self, *, campus: str, limit: int = 12) -> list[ScorecardSnapshot]:
        stmt = (
            select(ScorecardSnapshot)
            .where(ScorecardSnapshot.campus.ilike(f"%{campus}%"))
            .order_by(desc(ScorecardSnapshot.created_at), desc(ScorecardSnapshot.id))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def distinct_campuses(self) -> list[str]:
        from app.models.ad_copy import AdCopyGeneration as _Gen

        rows = self.db.execute(select(_Gen.campus).distinct()).all()
        return [r[0] for r in rows if r[0]]


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
