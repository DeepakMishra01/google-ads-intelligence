"""Repository for AI Ad Copy generation history."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.ad_copy import AdCopyGeneration, ApprovalEvent, ScorecardSnapshot
from app.repositories.base import BaseRepository


class ApprovalEventRepository(BaseRepository[ApprovalEvent]):
    model = ApprovalEvent

    def add_event(self, generation_id: int, event: str, actor: str | None, note: str | None):
        row = ApprovalEvent(generation_id=generation_id, event=event, actor=actor, note=note)
        self.db.add(row)
        self.db.flush()
        return row

    def for_generation(self, generation_id: int) -> list[ApprovalEvent]:
        stmt = (
            select(ApprovalEvent)
            .where(ApprovalEvent.generation_id == generation_id)
            .order_by(desc(ApprovalEvent.created_at), desc(ApprovalEvent.id))
        )
        return list(self.db.execute(stmt).scalars().all())


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

    def latest_per_campus(self) -> list[AdCopyGeneration]:
        """The newest generation for each campus — one row per campaign portfolio."""
        rows = self.db.execute(
            select(AdCopyGeneration).order_by(
                AdCopyGeneration.campus,
                desc(AdCopyGeneration.created_at),
                desc(AdCopyGeneration.id),
            )
        ).scalars().all()
        seen: dict[str, AdCopyGeneration] = {}
        for g in rows:
            if g.campus not in seen:
                seen[g.campus] = g
        return list(seen.values())
