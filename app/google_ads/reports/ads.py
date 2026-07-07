"""Ad (creative) config and daily metrics fetchers."""

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

GAQL_AD_CONFIG = """
SELECT
  ad_group_ad.ad.id,
  ad_group_ad.ad.type,
  ad_group_ad.status,
  ad_group_ad.policy_summary.approval_status,
  ad_group_ad.ad.final_urls,
  ad_group_ad.ad.responsive_search_ad.headlines,
  ad_group_ad.ad.responsive_search_ad.descriptions,
  ad_group.id,
  campaign.id
FROM ad_group_ad
WHERE ad_group_ad.status != 'REMOVED'
""".strip()


def _asset_texts(assets: Any) -> str | None:
    """Join responsive-ad asset ``.text`` values with newlines."""
    texts = [a.text for a in assets if getattr(a, "text", None)]
    return "\n".join(texts) if texts else None


def fetch_ads(factory: GoogleAdsClientFactory, customer_id: str) -> list[dict[str, Any]]:
    """Current-state ad config rows for upsert."""
    rows = factory.search(customer_id, GAQL_AD_CONFIG)
    out: list[dict[str, Any]] = []
    for r in rows:
        ad = r.ad_group_ad.ad
        rsa = ad.responsive_search_ad
        out.append(
            {
                "ad_id": int(ad.id),
                "ad_group_id": int(r.ad_group.id),
                "campaign_id": int(r.campaign.id),
                "type": enum_name(ad.type_),
                "status": enum_name(r.ad_group_ad.status),
                "approval_status": enum_name(r.ad_group_ad.policy_summary.approval_status),
                "final_urls": "\n".join(ad.final_urls) if ad.final_urls else None,
                "headlines": _asset_texts(rsa.headlines),
                "descriptions": _asset_texts(rsa.descriptions),
            }
        )
    return out


def fetch_ad_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (ad, date) for ad_snapshots."""
    query = f"""
    SELECT
      ad_group_ad.ad.id, ad_group.id, campaign.id,
      ad_group_ad.status, ad_group_ad.policy_summary.approval_status,
      segments.date,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions,
      metrics.video_views
    FROM ad_group_ad
    WHERE {gaql_date_between(start, end)} AND ad_group_ad.status != 'REMOVED'
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "ad_id": int(r.ad_group_ad.ad.id),
            "ad_group_id": int(r.ad_group.id),
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "status": enum_name(r.ad_group_ad.status),
            "approval_status": enum_name(r.ad_group_ad.policy_summary.approval_status),
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out
