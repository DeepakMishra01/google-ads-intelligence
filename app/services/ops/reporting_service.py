"""Reporting service (Module 10) - daily/weekly/monthly summaries in JSON/CSV/Excel."""

from __future__ import annotations

import csv
import io
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.repositories.dashboard import DashboardRepository
from app.services.ops.alerts_service import AlertsService
from app.services.ops.dates import resolve_ref_dates

Period = Literal["daily", "weekly", "monthly"]
_PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}

# Column order for tabular (CSV/Excel) exports of the campaign breakdown.
_CAMPAIGN_COLUMNS = [
    "campaign_id",
    "campaign_name",
    "status",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "ctr",
    "avg_cpc",
    "cost_per_conversion",
]


class ReportingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dashboard = DashboardRepository(db)
        self.alerts = AlertsService(db)

    def build_report(self, *, period: Period, account_id: int | None = None) -> dict[str, Any]:
        refs = resolve_ref_dates(self.db, account_id)
        start, end = refs.window(_PERIOD_DAYS[period])
        campaigns = self.dashboard.campaign_aggregates(
            start=start, end=end, account_id=account_id
        )
        campaigns.sort(key=lambda c: c["cost"], reverse=True)

        totals = {
            "impressions": sum(c["impressions"] for c in campaigns),
            "clicks": sum(c["clicks"] for c in campaigns),
            "cost": round(sum(c["cost"] for c in campaigns), 2),
            "conversions": round(sum(c["conversions"] for c in campaigns), 2),
        }
        impr, clk = totals["impressions"], totals["clicks"]
        totals["ctr"] = (clk / impr) if impr else None
        totals["avg_cpc"] = (totals["cost"] / clk) if clk else None

        return {
            "period": period,
            "start_date": start,
            "end_date": end,
            "account_id": account_id,
            "totals": totals,
            "campaign_count": len(campaigns),
            "campaigns": campaigns,
            "alerts": self.alerts.summary(account_id=account_id),
        }

    # --------------------------- renderers ----------------------------- #
    def render_csv(self, report: dict[str, Any]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CAMPAIGN_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in report["campaigns"]:
            writer.writerow(row)
        return buf.getvalue()

    def render_excel(self, report: dict[str, Any]) -> bytes:
        try:
            from openpyxl import Workbook
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openpyxl is required for Excel export.") from exc

        wb = Workbook()
        summary = wb.active
        summary.title = "Summary"
        summary.append(["Metric", "Value"])
        summary.append(["Period", report["period"]])
        summary.append(["Start", str(report["start_date"])])
        summary.append(["End", str(report["end_date"])])
        for key, val in report["totals"].items():
            summary.append([key, val])
        summary.append(["Open alerts", report["alerts"]["open_total"]])

        ws = wb.create_sheet("Campaigns")
        ws.append(_CAMPAIGN_COLUMNS)
        for row in report["campaigns"]:
            ws.append([row.get(col) for col in _CAMPAIGN_COLUMNS])

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
