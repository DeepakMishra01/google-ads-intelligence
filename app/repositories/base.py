"""Generic repository base with typed CRUD, upsert, and bulk-insert helpers.

Repositories own all database access. Services depend on repositories, never on
the ORM session directly. All methods operate within the caller's transaction;
repositories flush but never commit (commit is the service/session-scope's job).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """CRUD building blocks shared by every concrete repository."""

    model: type[ModelType]

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------ reads ------------------------------ #
    def get(self, id_: int) -> ModelType | None:
        return self.db.get(self.model, id_)

    def get_by(self, **filters: Any) -> ModelType | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int | None = 100,
        offset: int = 0,
        order_by: Any | None = None,
    ) -> list[ModelType]:
        stmt = select(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.filter_by(**filters)
        return int(self.db.execute(stmt).scalar_one())

    # ------------------------------ writes ----------------------------- #
    def add(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.flush()
        return obj

    def upsert(
        self, *, unique_by: dict[str, Any], values: dict[str, Any]
    ) -> tuple[ModelType, bool]:
        """Get-or-create by natural key, updating mutable fields if it exists.

        Returns ``(instance, created)``. DB-agnostic (works on SQLite in tests
        and Postgres in prod); appropriate for dimension tables whose row counts
        are modest. Snapshots use :meth:`bulk_insert` instead.
        """
        obj = self.get_by(**unique_by)
        if obj is None:
            obj = self.model(**unique_by, **values)
            self.db.add(obj)
            self.db.flush()
            return obj, True
        for key, val in values.items():
            setattr(obj, key, val)
        self.db.flush()
        return obj, False

    def bulk_insert(self, mappings: list[dict[str, Any]]) -> int:
        """Insert many rows in one statement. Returns the row count.

        Uses Core-level executemany so column ``default=`` values are applied for
        omitted columns. Intended for append-only snapshot tables.
        """
        if not mappings:
            return 0
        self.db.execute(insert(self.model), mappings)
        return len(mappings)

    def replace_window(
        self, mappings: list[dict[str, Any]], *, account_id: int, start: date, end: date
    ) -> int:
        """Idempotently refresh a snapshot window: delete the account's rows in
        [start, end] for this table, then insert the freshly fetched ones.

        Snapshots are append-only, but a sync re-run over an overlapping date range
        would otherwise stack duplicate (entity, day) rows and inflate every summed
        metric. Clearing the window first makes each sync deterministic — exactly one
        row per (entity, day). Runs inside the caller's transaction, so a failed
        insert rolls back the delete too (the old rows survive).
        """
        self.db.execute(
            delete(self.model).where(
                self.model.account_id == account_id,  # type: ignore[attr-defined]
                self.model.snapshot_date >= start,  # type: ignore[attr-defined]
                self.model.snapshot_date <= end,  # type: ignore[attr-defined]
            )
        )
        return self.bulk_insert(mappings)
