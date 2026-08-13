"""Weekly budget tracking: what an admin allotted per account vs actual spend.

Weeks run Monday–Sunday. ``overview`` returns per-account week-on-week
budget/spent/remaining (scoped to the caller's accounts); ``weekly_email_html``
renders the Monday summary sent to admins for the week just ended.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.campaign import CampaignSnapshot
from app.models.weekly_budget import AccountWeeklyBudget

_MICROS = 1_000_000


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _money(v: float | None) -> str:
    return "—" if v is None else f"₹{v:,.0f}"


class WeeklyBudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    def set_budget(
        self, *, account_id: int, week_start: date, amount: float, by: str | None
    ) -> dict[str, Any]:
        wk = _monday(week_start)
        row = self.db.execute(
            select(AccountWeeklyBudget).where(
                AccountWeeklyBudget.account_id == account_id,
                AccountWeeklyBudget.week_start == wk,
            )
        ).scalar_one_or_none()
        if row is None:
            row = AccountWeeklyBudget(account_id=account_id, week_start=wk,
                                      amount=amount, set_by=by)
            self.db.add(row)
        else:
            row.amount = amount
            row.set_by = by
        self.db.commit()
        return {"ok": True, "account_id": account_id,
                "week_start": wk.isoformat(), "amount": float(amount)}

    # ------------------------------------------------------------------ #
    def overview(
        self, *, allowed_account_ids: set[int] | None = None,
        weeks: int = 8, today: date | None = None,
    ) -> dict[str, Any]:
        today = today or date.today()
        this_monday = _monday(today)
        week_starts = sorted(this_monday - timedelta(weeks=i) for i in range(weeks))
        start, end = week_starts[0], this_monday + timedelta(days=6)

        acct_q = (
            select(Account.id, Account.descriptive_name, Account.customer_id)
            .where(Account.is_manager.isnot(True))
            .order_by(Account.descriptive_name.nulls_last(), Account.customer_id)
        )
        if allowed_account_ids is not None:
            acct_q = acct_q.where(Account.id.in_(allowed_account_ids))
        accounts = self.db.execute(acct_q).all()
        acct_ids = [a[0] for a in accounts]
        base = {"week_starts": [w.isoformat() for w in week_starts],
                "current_week": this_monday.isoformat(), "as_of": today.isoformat()}
        if not acct_ids:
            return {"accounts": [], **base}

        budgets: dict[tuple[int, date], float] = {}
        for aid, wk, amt in self.db.execute(
            select(AccountWeeklyBudget.account_id, AccountWeeklyBudget.week_start,
                   AccountWeeklyBudget.amount)
            .where(AccountWeeklyBudget.account_id.in_(acct_ids),
                   AccountWeeklyBudget.week_start >= start,
                   AccountWeeklyBudget.week_start <= this_monday)
        ):
            budgets[(aid, wk)] = float(amt)

        spend: dict[tuple[int, date], float] = defaultdict(float)
        for aid, d, cost in self.db.execute(
            select(CampaignSnapshot.account_id, CampaignSnapshot.snapshot_date,
                   func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0))
            .where(CampaignSnapshot.account_id.in_(acct_ids),
                   CampaignSnapshot.snapshot_date >= start,
                   CampaignSnapshot.snapshot_date <= end)
            .group_by(CampaignSnapshot.account_id, CampaignSnapshot.snapshot_date)
        ):
            spend[(aid, _monday(d))] += float(cost) / _MICROS

        out: list[dict[str, Any]] = []
        for aid, name, cid in accounts:
            rows = []
            for wk in week_starts:
                b = budgets.get((aid, wk))
                s = round(spend.get((aid, wk), 0.0), 2)
                rows.append({
                    "week_start": wk.isoformat(),
                    "budget": b,
                    "spent": s,
                    "remaining": round(b - s, 2) if b is not None else None,
                    "pct_used": round(s / b * 100, 1) if b else None,
                })
            out.append({"account_id": aid, "account_name": name or cid, "weeks": rows})
        return {"accounts": out, **base}

    # ------------------------------------------------------------------ #
    def weekly_email_html(self, *, today: date | None = None) -> tuple[str, str, str]:
        """(subject, text, html) summarising the week that just ended (Mon–Sun)."""
        today = today or date.today()
        last_week = _monday(today) - timedelta(weeks=1)
        ov = self.overview(weeks=2, today=today)
        label = f"{last_week.isoformat()} – {(last_week + timedelta(days=6)).isoformat()}"

        rows_html, t_b, t_s = [], 0.0, 0.0
        text_lines = [f"Weekly budget vs spend — week {label}", ""]
        for a in ov["accounts"]:
            wk = next((w for w in a["weeks"] if w["week_start"] == last_week.isoformat()), None)
            if not wk or (wk["budget"] is None and not wk["spent"]):
                continue
            b, s = wk["budget"], wk["spent"]
            rem = wk["remaining"]
            over = b is not None and s > b
            t_b += b or 0
            t_s += s or 0
            colour = "#dc2626" if over else "#0f172a"
            rows_html.append(
                f"<tr><td style='padding:6px 10px;border-top:1px solid #eef2f7'>{a['account_name']}</td>"
                f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right'>{_money(b)}</td>"
                f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right'>{_money(s)}</td>"
                f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right;color:{colour}'>"
                f"{_money(rem)}</td>"
                f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right'>"
                f"{'' if wk['pct_used'] is None else str(wk['pct_used']) + '%'}</td></tr>"
            )
            text_lines.append(f"{a['account_name']}: budget {_money(b)}, spent {_money(s)}, "
                              f"remaining {_money(rem)}")

        subject = f"Weekly budget vs spend — {label}"
        html = f"""\
<div style="background:#f1f5f9;padding:24px 12px;font-family:Arial,Helvetica,sans-serif">
 <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;
      box-shadow:0 1px 4px rgba(15,23,42,.08)">
  <div style="background:#4f46e5;color:#fff;padding:16px 22px;font-weight:bold;font-size:16px">
    Weekly budget vs spend · {label}</div>
  <div style="padding:20px">
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr style="background:#f8fafc"><th style="padding:7px 10px;text-align:left">Account</th>
        <th style="padding:7px 10px;text-align:right">Budget</th>
        <th style="padding:7px 10px;text-align:right">Spent</th>
        <th style="padding:7px 10px;text-align:right">Remaining</th>
        <th style="padding:7px 10px;text-align:right">Used</th></tr>
      {''.join(rows_html) or '<tr><td style="padding:10px;color:#64748b">No budgets set for this week.</td></tr>'}
      <tr style="background:#f8fafc;font-weight:bold">
        <td style="padding:7px 10px">Total</td>
        <td style="padding:7px 10px;text-align:right">{_money(t_b)}</td>
        <td style="padding:7px 10px;text-align:right">{_money(t_s)}</td>
        <td style="padding:7px 10px;text-align:right">{_money(t_b - t_s)}</td>
        <td style="padding:7px 10px;text-align:right">
          {'' if not t_b else str(round(t_s / t_b * 100, 1)) + '%'}</td></tr>
    </table>
    <p style="font-size:12px;color:#94a3b8;margin-top:16px">Remaining in red means the account
      overspent its weekly budget. Set next week's budgets in Command Center → Weekly Budgets.</p>
  </div>
 </div>
</div>"""
        return subject, "\n".join(text_lines), html
