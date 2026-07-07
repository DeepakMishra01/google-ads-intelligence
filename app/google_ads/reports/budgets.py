"""Campaign budget config and daily utilization fetchers."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.google_ads.client import GoogleAdsClientFactory
from app.google_ads.reports._helpers import (
    enum_name,
    gaql_date_between,
    parse_ads_date,
)

GAQL_BUDGET_CONFIG = """
SELECT
  campaign_budget.id,
  campaign_budget.name,
  campaign_budget.amount_micros,
  campaign_budget.delivery_method,
  campaign_budget.period,
  campaign_budget.explicitly_shared
FROM campaign_budget
""".strip()


def fetch_budgets(factory: GoogleAdsClientFactory, customer_id: str) -> list[dict[str, Any]]:
    """Current-state budget config rows for upsert."""
    rows = factory.search(customer_id, GAQL_BUDGET_CONFIG)
    out: list[dict[str, Any]] = []
    for r in rows:
        b = r.campaign_budget
        out.append(
            {
                "budget_id": int(b.id),
                "name": b.name or None,
                "amount_micros": int(b.amount_micros) if b.amount_micros else None,
                "delivery_method": enum_name(b.delivery_method),
                "period": enum_name(b.period),
                "explicitly_shared": bool(b.explicitly_shared),
            }
        )
    return out


def fetch_budget_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (budget, date) with amount + spend for budget_snapshots."""
    query = f"""
    SELECT
      campaign_budget.id,
      campaign_budget.amount_micros,
      campaign_budget.delivery_method,
      segments.date,
      metrics.cost_micros
    FROM campaign_budget
    WHERE {gaql_date_between(start, end)}
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        amount = int(r.campaign_budget.amount_micros) if r.campaign_budget.amount_micros else None
        spend = int(r.metrics.cost_micros or 0)
        utilization = (spend / amount) if amount else None
        out.append(
            {
                "budget_id": int(r.campaign_budget.id),
                "snapshot_date": parse_ads_date(r.segments.date),
                "amount_micros": amount,
                "spend_micros": spend,
                "utilization": round(utilization, 4) if utilization is not None else None,
                "delivery_method": enum_name(r.campaign_budget.delivery_method),
            }
        )
    return out
