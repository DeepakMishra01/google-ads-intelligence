"""Campaign budget dimension + budget snapshot tables."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, SnapshotMixin, TimestampMixin


class Budget(IntPKMixin, TimestampMixin, Base):
    """Current known configuration of a campaign budget (shared budgets included)."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("account_id", "budget_id", name="budgets_account_budget"),)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    budget_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Google id

    name: Mapped[str | None] = mapped_column(String(512))
    amount_micros: Mapped[int | None] = mapped_column(BigInteger)
    delivery_method: Mapped[str | None] = mapped_column(String(32))
    period: Mapped[str | None] = mapped_column(String(32))
    explicitly_shared: Mapped[bool | None]

    snapshots: Mapped[list[BudgetSnapshot]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetSnapshot(IntPKMixin, SnapshotMixin, Base):
    """Append-only daily snapshot of a budget's amount and utilization."""

    __tablename__ = "budget_snapshots"

    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id", ondelete="CASCADE"), index=True)
    amount_micros: Mapped[int | None] = mapped_column(BigInteger)
    # Spend against this budget on the snapshot date (from associated campaigns).
    spend_micros: Mapped[int | None] = mapped_column(BigInteger)
    utilization: Mapped[float | None] = mapped_column(Numeric(10, 4))  # spend / amount
    delivery_method: Mapped[str | None] = mapped_column(String(32))

    budget: Mapped[Budget] = relationship(back_populates="snapshots")
