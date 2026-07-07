"""Budget Monitoring service (Module 6)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config.ops_rules import get_ops_rules
from app.repositories.ops import OpsRepository
from app.services.ops.dates import fraction_of_day_elapsed
from app.services.ops.scoring import compute_budget_risk


class BudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OpsRepository(db)
        self.rules = get_ops_rules()

    def monitoring(self, *, account_id: int | None = None) -> list[dict[str, Any]]:
        # For a completed day the whole day has elapsed (projection == spend);
        # for the live calendar day we linearly project from the elapsed fraction.
        today = date.today()
        rows: list[dict[str, Any]] = []
        for b in self.repo.latest_budget_snapshots(account_id):
            elapsed = (
                fraction_of_day_elapsed() if b["snapshot_date"] == today else 1.0
            )
            risk = compute_budget_risk(
                daily_budget=b["amount"],
                spend_so_far=b["spend"],
                fraction_of_day_elapsed=elapsed,
                rules=self.rules.budget,
            )
            rows.append(
                {
                    "budget_pk": b["budget_pk"],
                    "name": b["name"],
                    "account_id": b["account_id"],
                    "snapshot_date": b["snapshot_date"],
                    "budget": b["amount"],
                    "current_spend": b["spend"],
                    "remaining_budget": round(max(0.0, b["amount"] - b["spend"]), 2),
                    "utilization": (
                        round(risk.utilization, 4) if risk.utilization is not None else None
                    ),
                    "projected_eod_spend": risk.projected_eod_spend,
                    "risk": risk.risk,
                }
            )
        # Riskiest first.
        order = {"critical": 0, "warning": 1, "healthy": 2}
        rows.sort(key=lambda r: (order.get(r["risk"], 3), -(r["utilization"] or 0)))
        return rows
