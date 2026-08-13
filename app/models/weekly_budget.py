"""Weekly budget an admin allocates to an account (the budget 'given' to the AM).

One row per (account, ISO week starting Monday). Actual spend is read from
``CampaignSnapshot`` for the same week; remaining = budget - spent.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin


class AccountWeeklyBudget(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "account_weekly_budgets"
    __table_args__ = (
        UniqueConstraint("account_id", "week_start", name="account_weekly_budget_uq"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    week_start: Mapped[date] = mapped_column(Date, index=True)  # Monday of the week
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    set_by: Mapped[str | None] = mapped_column(String(160))  # admin email/name
