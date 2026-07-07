"""Ad group config and daily metrics fetchers."""

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

GAQL_AD_GROUP_CONFIG = """
SELECT
  ad_group.id,
  ad_group.name,
  ad_group.status,
  ad_group.type,
  ad_group.cpc_bid_micros,
  campaign.id
FROM ad_group
WHERE ad_group.status != 'REMOVED'
""".strip()


def fetch_ad_groups(factory: GoogleAdsClientFactory, customer_id: str) -> list[dict[str, Any]]:
    """Current-state ad group config rows for upsert."""
    rows = factory.search(customer_id, GAQL_AD_GROUP_CONFIG)
    out: list[dict[str, Any]] = []
    for r in rows:
        ag = r.ad_group
        out.append(
            {
                "ad_group_id": int(ag.id),
                "campaign_id": int(r.campaign.id),
                "name": ag.name or None,
                "status": enum_name(ag.status),
                "type": enum_name(ag.type_),
                "cpc_bid_micros": int(ag.cpc_bid_micros) if ag.cpc_bid_micros else None,
            }
        )
    return out


def fetch_ad_group_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (ad group, date) for ad_group_snapshots."""
    query = f"""
    SELECT
      ad_group.id, campaign.id, ad_group.status, ad_group.cpc_bid_micros,
      segments.date,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions,
      metrics.video_views
    FROM ad_group
    WHERE {gaql_date_between(start, end)} AND ad_group.status != 'REMOVED'
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "ad_group_id": int(r.ad_group.id),
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "status": enum_name(r.ad_group.status),
            "cpc_bid_micros": int(r.ad_group.cpc_bid_micros) if r.ad_group.cpc_bid_micros else None,
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out
