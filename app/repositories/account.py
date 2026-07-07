"""Account repository."""

from __future__ import annotations

from sqlalchemy import select

from app.models.account import Account
from app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    model = Account

    def get_by_customer_id(self, customer_id: str) -> Account | None:
        return self.get_by(customer_id=customer_id)

    def upsert_account(self, data: dict) -> tuple[Account, bool]:
        customer_id = data["customer_id"]
        values = {k: v for k, v in data.items() if k != "customer_id"}
        return self.upsert(unique_by={"customer_id": customer_id}, values=values)

    def list_syncable(self) -> list[Account]:
        """Non-manager accounts flagged for scheduled syncing."""
        stmt = select(Account).where(Account.is_manager.is_(False), Account.is_syncable.is_(True))
        return list(self.db.execute(stmt).scalars().all())
