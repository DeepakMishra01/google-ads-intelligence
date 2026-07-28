"""Keyword config and daily metrics fetchers, including Quality Score history."""

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

GAQL_KEYWORD_CONFIG = """
SELECT
  ad_group_criterion.criterion_id,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  ad_group_criterion.status,
  ad_group_criterion.cpc_bid_micros,
  ad_group.id,
  campaign.id
FROM keyword_view
WHERE ad_group_criterion.status != 'REMOVED'
""".strip()


def fetch_keywords(factory: GoogleAdsClientFactory, customer_id: str) -> list[dict[str, Any]]:
    """Current-state keyword config rows for upsert."""
    rows = factory.search(customer_id, GAQL_KEYWORD_CONFIG)
    out: list[dict[str, Any]] = []
    for r in rows:
        crit = r.ad_group_criterion
        out.append(
            {
                "criterion_id": int(crit.criterion_id),
                "ad_group_id": int(r.ad_group.id),
                "campaign_id": int(r.campaign.id),
                "text": crit.keyword.text or None,
                "match_type": enum_name(crit.keyword.match_type),
                "status": enum_name(crit.status),
                "cpc_bid_micros": int(crit.cpc_bid_micros) if crit.cpc_bid_micros else None,
            }
        )
    return out


def fetch_keyword_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (keyword, date) for keyword_snapshots (with Quality Score)."""
    query = f"""
    SELECT
      ad_group_criterion.criterion_id,
      ad_group.id, campaign.id,
      ad_group_criterion.keyword.match_type,
      ad_group_criterion.status,
      ad_group_criterion.quality_info.quality_score,
      ad_group_criterion.quality_info.creative_quality_score,
      ad_group_criterion.quality_info.post_click_quality_score,
      ad_group_criterion.quality_info.search_predicted_ctr,
      segments.date,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions
    FROM keyword_view
    WHERE {gaql_date_between(start, end)} AND ad_group_criterion.status != 'REMOVED'
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        crit = r.ad_group_criterion
        qi = crit.quality_info
        row = {
            "criterion_id": int(crit.criterion_id),
            "ad_group_id": int(r.ad_group.id),
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "match_type": enum_name(crit.keyword.match_type),
            "status": enum_name(crit.status),
            "quality_score": int(qi.quality_score) if qi.quality_score else None,
            # Quality Score sub-components (enum name strings).
            "ad_relevance": enum_name(qi.creative_quality_score),
            "landing_page_experience": enum_name(qi.post_click_quality_score),
            "expected_ctr": enum_name(qi.search_predicted_ctr),
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out
