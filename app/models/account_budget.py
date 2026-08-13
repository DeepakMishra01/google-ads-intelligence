"""Account-level budget an admin allocates (monthly + all-time total).

One table, two kinds:
- ``period='month'`` → a calendar-month budget; ``period_start`` = 1st of the month.
- ``period='total'`` → the all-time total allocated to the account; ``period_start``
  is the sentinel 1900-01-01 (so the unique constraint holds without NULLs).

Actual spend is read from ``CampaignSnapshot`` (this is an allocation, not a cap).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin

TOTAL_SENTINEL = date(1900, 1, 1)


class AccountBudget(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "account_budgets"
    __table_args__ = (
        UniqueConstraint("account_id", "period", "period_start", name="account_budget_uq"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str] = mapped_column(String(8))  # 'month' | 'total'
    period_start: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(16, 2))
    set_by: Mapped[str | None] = mapped_column(String(160))
