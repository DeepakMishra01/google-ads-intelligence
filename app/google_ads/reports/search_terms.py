"""Search term (user query) fetcher.

Search terms are inherently date-segmented report rows; a single query returns
both the dimension identity (query + ad group) and the daily metrics.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.google_ads.client import GoogleAdsClientFactory
from app.google_ads.reports._helpers import (
    enum_name,
    gaql_date_between,
    metrics_dict,
    parse_ads_date,
)


def fetch_search_terms(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (query, ad group, date). Carries both dimension + metrics."""
    query = f"""
    SELECT
      search_term_view.search_term,
      search_term_view.status,
      segments.search_term_match_type,
      segments.date,
      ad_group.id, campaign.id,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions,
      metrics.video_views
    FROM search_term_view
    WHERE {gaql_date_between(start, end)}
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "query": r.search_term_view.search_term or "",
            "search_term_targeting_status": enum_name(r.search_term_view.status),
            "match_type": enum_name(r.segments.search_term_match_type),
            "ad_group_id": int(r.ad_group.id),
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out
