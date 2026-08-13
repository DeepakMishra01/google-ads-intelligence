"""Account-level budgets: monthly + all-time total allocated vs spent vs remaining.

Additive to the per-campus AI plan budgets — this is the admin's account-level
allocation ('total budget given to the account'), set on the Accountability tab.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.account_budget import TOTAL_SENTINEL, AccountBudget
from app.models.campaign import CampaignSnapshot
from app.models.user import User, UserAccount

_MICROS = 1_000_000


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _row(budget: float | None, spent: float) -> dict[str, Any]:
    return {
        "budget": budget,
        "spent": round(spent, 2),
        "remaining": round(budget - spent, 2) if budget is not None else None,
        "pct_used": round(spent / budget * 100, 1) if budget else None,
    }


class AccountBudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    def set_budget(
        self, *, account_id: int, period: str, amount: float,
        period_start: date | None = None, by: str | None = None,
    ) -> dict[str, Any]:
        if period not in ("month", "total"):
            return {"ok": False, "reason": "period must be 'month' or 'total'"}
        ps = TOTAL_SENTINEL if period == "total" else _first_of_month(period_start or date.today())
        row = self.db.execute(
            select(AccountBudget).where(
                AccountBudget.account_id == account_id,
                AccountBudget.period == period,
                AccountBudget.period_start == ps,
            )
        ).scalar_one_or_none()
        if row is None:
            row = AccountBudget(account_id=account_id, period=period,
                                period_start=ps, amount=amount, set_by=by)
            self.db.add(row)
        else:
            row.amount = amount
            row.set_by = by
        self.db.commit()
        return {"ok": True, "account_id": account_id, "period": period,
                "period_start": ps.isoformat(), "amount": float(amount)}

    # ------------------------------------------------------------------ #
    def _spend(self, acct_ids: list[int], start: date | None, end: date) -> dict[int, float]:
        conds = [CampaignSnapshot.account_id.in_(acct_ids), CampaignSnapshot.snapshot_date <= end]
        if start is not None:
            conds.append(CampaignSnapshot.snapshot_date >= start)
        out: dict[int, float] = defaultdict(float)
        for aid, cost in self.db.execute(
            select(CampaignSnapshot.account_id,
                   func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0))
            .where(*conds).group_by(CampaignSnapshot.account_id)
        ):
            out[aid] = float(cost) / _MICROS
        return out

    def overview(
        self, *, allowed_account_ids: set[int] | None = None, today: date | None = None
    ) -> dict[str, Any]:
        today = today or date.today()
        month_start = _first_of_month(today)

        acct_q = (
            select(Account.id, Account.descriptive_name, Account.customer_id)
            .where(Account.is_manager.isnot(True))
            .order_by(Account.descriptive_name.nulls_last(), Account.customer_id)
        )
        if allowed_account_ids is not None:
            acct_q = acct_q.where(Account.id.in_(allowed_account_ids))
        accounts = self.db.execute(acct_q).all()
        acct_ids = [a[0] for a in accounts]
        base = {"month_start": month_start.isoformat(), "as_of": today.isoformat()}
        if not acct_ids:
            return {"accounts": [], **base}

        monthly: dict[int, float] = {}
        total: dict[int, float] = {}
        for aid, period, ps, amt in self.db.execute(
            select(AccountBudget.account_id, AccountBudget.period,
                   AccountBudget.period_start, AccountBudget.amount)
            .where(AccountBudget.account_id.in_(acct_ids))
        ):
            if period == "total":
                total[aid] = float(amt)
            elif ps == month_start:
                monthly[aid] = float(amt)

        month_spend = self._spend(acct_ids, month_start, today)
        alltime_spend = self._spend(acct_ids, None, today)

        managers: dict[int, list[str]] = defaultdict(list)
        for aid, name, email in self.db.execute(
            select(UserAccount.account_id, User.full_name, User.email)
            .join(User, UserAccount.user_id == User.id)
            .where(UserAccount.account_id.in_(acct_ids), User.is_active.is_(True))
        ):
            managers[aid].append(name or email)

        out = []
        for aid, name, cid in accounts:
            out.append({
                "account_id": aid,
                "account_name": name or cid,
                "manager": ", ".join(sorted(managers.get(aid, []))) or "Unassigned",
                "monthly": _row(monthly.get(aid), month_spend.get(aid, 0.0)),
                "total": _row(total.get(aid), alltime_spend.get(aid, 0.0)),
            })
        return {"accounts": out, **base}

    def maps_for_email(self, acct_ids: list[int], today: date) -> dict[str, Any]:
        """Compact per-account monthly + total dicts for the weekly email."""
        if not acct_ids:
            return {"monthly": {}, "total": {}, "month_spend": {}, "alltime_spend": {}}
        month_start = _first_of_month(today)
        monthly: dict[int, float] = {}
        total: dict[int, float] = {}
        for aid, period, ps, amt in self.db.execute(
            select(AccountBudget.account_id, AccountBudget.period,
                   AccountBudget.period_start, AccountBudget.amount)
            .where(AccountBudget.account_id.in_(acct_ids))
        ):
            if period == "total":
                total[aid] = float(amt)
            elif ps == month_start:
                monthly[aid] = float(amt)
        return {
            "monthly": monthly,
            "total": total,
            "month_spend": self._spend(acct_ids, month_start, today),
            "alltime_spend": self._spend(acct_ids, None, today),
        }
