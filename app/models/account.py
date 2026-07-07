"""Account (Google Ads customer) dimension table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class Account(IntPKMixin, TimestampMixin, Base):
    """A Google Ads customer account (client account under the MCC, or the MCC)."""

    __tablename__ = "accounts"

    # Google Ads customer id (digits only). The stable natural key.
    customer_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    descriptive_name: Mapped[str | None] = mapped_column(String(255))
    currency_code: Mapped[str | None] = mapped_column(String(8))
    time_zone: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))

    # MCC / hierarchy metadata.
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    manager_customer_id: Mapped[str | None] = mapped_column(String(20), index=True)
    test_account: Mapped[bool | None] = mapped_column(Boolean)
    auto_tagging_enabled: Mapped[bool | None] = mapped_column(Boolean)

    # Whether the sync engine should include this account in scheduled syncs.
    is_syncable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    campaigns: Mapped[list[Campaign]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Account {self.customer_id} {self.descriptive_name!r}>"
