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
from app.models.user import User, UserAccount
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

        # Per (account, week): spend + impressions + clicks + conversions.
        metrics: dict[tuple[int, date], dict[str, float]] = defaultdict(
            lambda: {"spent": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0}
        )
        for aid, d, cost, impr, clk, conv in self.db.execute(
            select(CampaignSnapshot.account_id, CampaignSnapshot.snapshot_date,
                   func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
                   func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
                   func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
                   func.coalesce(func.sum(CampaignSnapshot.conversions), 0))
            .where(CampaignSnapshot.account_id.in_(acct_ids),
                   CampaignSnapshot.snapshot_date >= start,
                   CampaignSnapshot.snapshot_date <= end)
            .group_by(CampaignSnapshot.account_id, CampaignSnapshot.snapshot_date)
        ):
            m = metrics[(aid, _monday(d))]
            m["spent"] += float(cost) / _MICROS
            m["impressions"] += int(impr or 0)
            m["clicks"] += int(clk or 0)
            m["conversions"] += float(conv or 0)

        # Assigned account manager(s) per account (explicit grants in Users & Access).
        managers: dict[int, list[str]] = defaultdict(list)
        for aid, name, email in self.db.execute(
            select(UserAccount.account_id, User.full_name, User.email)
            .join(User, UserAccount.user_id == User.id)
            .where(UserAccount.account_id.in_(acct_ids), User.is_active.is_(True))
        ):
            managers[aid].append(name or email)

        out: list[dict[str, Any]] = []
        for aid, name, cid in accounts:
            rows = []
            for wk in week_starts:
                b = budgets.get((aid, wk))
                m = metrics.get((aid, wk)) or {"spent": 0.0, "impressions": 0,
                                               "clicks": 0, "conversions": 0.0}
                s = round(m["spent"], 2)
                impr, clk = int(m["impressions"]), int(m["clicks"])
                conv = round(m["conversions"], 1)
                rows.append({
                    "week_start": wk.isoformat(),
                    "budget": b,
                    "spent": s,
                    "remaining": round(b - s, 2) if b is not None else None,
                    "pct_used": round(s / b * 100, 1) if b else None,
                    "impressions": impr,
                    "clicks": clk,
                    "conversions": conv,
                    "ctr": round(clk / impr, 4) if impr else None,
                    "cpm": round(s / impr * 1000, 2) if impr else None,
                    "cpl": round(s / conv, 0) if conv else None,
                })
            out.append({
                "account_id": aid,
                "account_name": name or cid,
                "manager": ", ".join(sorted(managers.get(aid, []))) or "Unassigned",
                "weeks": rows,
            })
        return {"accounts": out, **base}

    # ------------------------------------------------------------------ #
    def weekly_email_html(self, *, today: date | None = None) -> tuple[str, str, str]:
        """(subject, text, html) summarising the week that just ended (Mon–Sun)."""
        today = today or date.today()
        last_week = _monday(today) - timedelta(weeks=1)
        ov = self.overview(weeks=2, today=today)
        label = f"{last_week.isoformat()} – {(last_week + timedelta(days=6)).isoformat()}"

        def _num(v: float | int | None) -> str:
            return "—" if v is None else f"{int(round(v)):,}"

        def _pct(v: float | None) -> str:
            return "—" if v is None else f"{round(v * 100, 1)}%"

        rows_html: list[str] = []
        t_b = t_s = t_impr = t_clk = t_conv = 0.0
        text_lines = [f"Weekly budget vs spend — week {label}", ""]
        cell = "padding:6px 8px;border-top:1px solid #eef2f7;text-align:right;font-variant-numeric:tabular-nums"
        for a in ov["accounts"]:
            wk = next((w for w in a["weeks"] if w["week_start"] == last_week.isoformat()), None)
            if not wk or (wk["budget"] is None and not wk["spent"] and not wk["impressions"]):
                continue
            b, s, rem = wk["budget"], wk["spent"], wk["remaining"]
            over = b is not None and s > b
            t_b += b or 0
            t_s += s or 0
            t_impr += wk["impressions"]
            t_clk += wk["clicks"]
            t_conv += wk["conversions"]
            colour = "#dc2626" if over else "#0f172a"
            rows_html.append(
                f"<tr>"
                f"<td style='padding:6px 8px;border-top:1px solid #eef2f7'>{a['account_name']}</td>"
                f"<td style='padding:6px 8px;border-top:1px solid #eef2f7;color:#64748b'>{a['manager']}</td>"
                f"<td style='{cell}'>{_money(b)}</td>"
                f"<td style='{cell}'>{_money(s)}</td>"
                f"<td style='{cell};color:{colour}'>{_money(rem)}</td>"
                f"<td style='{cell}'>{_num(wk['impressions'])}</td>"
                f"<td style='{cell}'>{_num(wk['clicks'])}</td>"
                f"<td style='{cell}'>{_num(wk['conversions'])}</td>"
                f"<td style='{cell}'>{_pct(wk['ctr'])}</td>"
                f"<td style='{cell}'>{_money(wk['cpm'])}</td>"
                f"<td style='{cell}'>{_money(wk['cpl'])}</td></tr>"
            )
            text_lines.append(
                f"{a['account_name']} ({a['manager']}): budget {_money(b)}, spent {_money(s)}, "
                f"remaining {_money(rem)}, impr {_num(wk['impressions'])}, clicks {_num(wk['clicks'])}, "
                f"leads {_num(wk['conversions'])}"
            )

        t_ctr = t_clk / t_impr if t_impr else None
        t_cpm = t_s / t_impr * 1000 if t_impr else None
        t_cpl = t_s / t_conv if t_conv else None
        head = ("padding:7px 8px;text-align:right;font-size:12px;color:#64748b")
        subject = f"Weekly budget vs spend — {label}"
        html = f"""\
<div style="background:#f1f5f9;padding:24px 12px;font-family:Arial,Helvetica,sans-serif">
 <div style="max-width:920px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;
      box-shadow:0 1px 4px rgba(15,23,42,.08)">
  <div style="background:#4f46e5;color:#fff;padding:16px 22px;font-weight:bold;font-size:16px">
    Weekly budget vs spend · {label}</div>
  <div style="padding:20px;overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr style="background:#f8fafc">
        <th style="padding:7px 8px;text-align:left;font-size:12px;color:#64748b">Account</th>
        <th style="padding:7px 8px;text-align:left;font-size:12px;color:#64748b">Manager</th>
        <th style="{head}">Budget</th><th style="{head}">Spent</th><th style="{head}">Remaining</th>
        <th style="{head}">Impr.</th><th style="{head}">Clicks</th><th style="{head}">Leads</th>
        <th style="{head}">CTR</th><th style="{head}">CPM</th><th style="{head}">CPL</th></tr>
      {''.join(rows_html) or '<tr><td colspan="11" style="padding:10px;color:#64748b">No account activity or budgets for this week.</td></tr>'}
      <tr style="background:#f8fafc;font-weight:bold">
        <td style="padding:7px 8px">Total</td><td style="padding:7px 8px"></td>
        <td style="{cell}">{_money(t_b)}</td><td style="{cell}">{_money(t_s)}</td>
        <td style="{cell}">{_money(t_b - t_s)}</td>
        <td style="{cell}">{_num(t_impr)}</td><td style="{cell}">{_num(t_clk)}</td>
        <td style="{cell}">{_num(t_conv)}</td><td style="{cell}">{_pct(t_ctr)}</td>
        <td style="{cell}">{_money(t_cpm)}</td><td style="{cell}">{_money(t_cpl)}</td></tr>
    </table>
    <p style="font-size:12px;color:#94a3b8;margin-top:16px">Remaining in red = overspent the weekly
      budget. Leads = tracked conversions (0 where tracking isn't set up). Set budgets in Command
      Center → Weekly Budgets.</p>
  </div>
 </div>
</div>"""
        return subject, "\n".join(text_lines), html
