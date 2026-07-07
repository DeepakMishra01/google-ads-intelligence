"""Budget dimension + snapshot repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.budget import Budget, BudgetSnapshot
from app.repositories.base import BaseRepository


class BudgetRepository(BaseRepository[Budget]):
    model = Budget

    def upsert_budget(self, account_id: int, data: dict) -> tuple[Budget, bool]:
        budget_id = data["budget_id"]
        values = {k: v for k, v in data.items() if k != "budget_id"}
        return self.upsert(
            unique_by={"account_id": account_id, "budget_id": budget_id}, values=values
        )

    def google_id_to_pk(self, account_id: int) -> dict[int, int]:
        stmt = select(Budget.budget_id, Budget.id).where(Budget.account_id == account_id)
        return {int(g): int(pk) for g, pk in self.db.execute(stmt).all()}


class BudgetSnapshotRepository(BaseRepository[BudgetSnapshot]):
    model = BudgetSnapshot
