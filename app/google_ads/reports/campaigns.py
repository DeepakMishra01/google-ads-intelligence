"""Campaign config, daily metrics, and device/geo performance fetchers."""

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

GAQL_CAMPAIGN_CONFIG = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.serving_status,
  campaign.advertising_channel_type,
  campaign.advertising_channel_sub_type,
  campaign.bidding_strategy_type,
  campaign.network_settings.target_google_search,
  campaign.network_settings.target_search_network,
  campaign.network_settings.target_content_network,
  campaign.network_settings.target_partner_search_network,
  campaign.optimization_score,
  campaign_budget.id
FROM campaign
WHERE campaign.status != 'REMOVED'
""".strip()


def _networks(row: Any) -> str | None:
    ns = row.campaign.network_settings
    flags = [
        ("GOOGLE_SEARCH", ns.target_google_search),
        ("SEARCH_PARTNERS", ns.target_search_network),
        ("CONTENT", ns.target_content_network),
        ("PARTNER_SEARCH", ns.target_partner_search_network),
    ]
    enabled = [name for name, on in flags if on]
    return ",".join(enabled) if enabled else None


def fetch_campaigns(factory: GoogleAdsClientFactory, customer_id: str) -> list[dict[str, Any]]:
    """Current-state campaign config rows for upsert."""
    rows = factory.search(customer_id, GAQL_CAMPAIGN_CONFIG)
    out: list[dict[str, Any]] = []
    for r in rows:
        c = r.campaign
        out.append(
            {
                "campaign_id": int(c.id),
                "name": c.name or None,
                "status": enum_name(c.status),
                "serving_status": enum_name(c.serving_status),
                "advertising_channel_type": enum_name(c.advertising_channel_type),
                "advertising_channel_sub_type": enum_name(c.advertising_channel_sub_type),
                "bidding_strategy_type": enum_name(c.bidding_strategy_type),
                "networks": _networks(r),
                # start_date/end_date removed from the query for Google Ads API v24
                # compatibility (fields not recognized there); not needed downstream.
                "start_date": None,
                "end_date": None,
                "optimization_score": float(c.optimization_score) if c.optimization_score else None,
                "budget_id": int(r.campaign_budget.id) if r.campaign_budget.id else None,
            }
        )
    return out


def fetch_campaign_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (campaign, date) for campaign_snapshots."""
    query = f"""
    SELECT
      campaign.id,
      campaign.status,
      campaign.bidding_strategy_type,
      campaign.optimization_score,
      campaign_budget.amount_micros,
      segments.date,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions
    FROM campaign
    WHERE {gaql_date_between(start, end)} AND campaign.status != 'REMOVED'
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "status": enum_name(r.campaign.status),
            "bidding_strategy_type": enum_name(r.campaign.bidding_strategy_type),
            "optimization_score": float(r.campaign.optimization_score)
            if r.campaign.optimization_score
            else None,
            "budget_micros": int(r.campaign_budget.amount_micros)
            if r.campaign_budget.amount_micros
            else None,
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out


def fetch_campaign_device_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (campaign, date, device) for campaign_device_snapshots."""
    query = f"""
    SELECT
      campaign.id, segments.date, segments.device,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions
    FROM campaign
    WHERE {gaql_date_between(start, end)} AND campaign.status != 'REMOVED'
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "device": enum_name(r.segments.device) or "UNKNOWN",
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out


def fetch_campaign_geo_metrics(
    factory: GoogleAdsClientFactory, customer_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """One dict per (campaign, date, country) for campaign_geo_snapshots."""
    query = f"""
    SELECT
      campaign.id, segments.date,
      geographic_view.country_criterion_id,
      metrics.impressions, metrics.clicks, metrics.interactions, metrics.cost_micros,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.conversions, metrics.conversions_value, metrics.all_conversions
    FROM geographic_view
    WHERE {gaql_date_between(start, end)}
    """.strip()
    rows = factory.search(customer_id, query)
    out: list[dict[str, Any]] = []
    for r in rows:
        cid = r.geographic_view.country_criterion_id
        row = {
            "campaign_id": int(r.campaign.id),
            "snapshot_date": parse_ads_date(r.segments.date),
            "country_criterion_id": int(cid) if cid else None,
            "location_name": None,
        }
        row.update(metrics_dict(r))
        out.append(row)
    return out
