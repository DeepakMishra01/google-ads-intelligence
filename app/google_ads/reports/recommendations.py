"""Recommendation fetcher.

Recommendations are point-in-time optimization suggestions from Google. Each
sync captures the currently active set as append-only snapshot rows.
"""

from __future__ import annotations

import json
from typing import Any

from app.google_ads.client import GoogleAdsClientFactory
from app.google_ads.reports._helpers import enum_name

GAQL_RECOMMENDATIONS = """
SELECT
  recommendation.resource_name,
  recommendation.type,
  recommendation.dismissed,
  campaign.id,
  recommendation.impact.base_metrics.impressions,
  recommendation.impact.base_metrics.clicks,
  recommendation.impact.base_metrics.cost_micros,
  recommendation.impact.base_metrics.conversions,
  recommendation.impact.potential_metrics.impressions,
  recommendation.impact.potential_metrics.clicks,
  recommendation.impact.potential_metrics.cost_micros,
  recommendation.impact.potential_metrics.conversions
FROM recommendation
""".strip()


def fetch_recommendations(
    factory: GoogleAdsClientFactory, customer_id: str
) -> list[dict[str, Any]]:
    """Return currently active recommendations for the account."""
    rows = factory.search(customer_id, GAQL_RECOMMENDATIONS)
    out: list[dict[str, Any]] = []
    for r in rows:
        rec = r.recommendation
        base = rec.impact.base_metrics
        pot = rec.impact.potential_metrics
        campaign_gid = int(r.campaign.id) if r.campaign.id else None
        out.append(
            {
                "resource_name": rec.resource_name,
                "recommendation_type": enum_name(rec.type_),
                "campaign_google_id": campaign_gid,
                "impact_base_cost_micros": int(base.cost_micros) if base.cost_micros else None,
                "impact_potential_cost_micros": int(pot.cost_micros) if pot.cost_micros else None,
                "impact_base_clicks": float(base.clicks) if base.clicks else None,
                "impact_potential_clicks": float(pot.clicks) if pot.clicks else None,
                "impact_base_conversions": float(base.conversions) if base.conversions else None,
                "impact_potential_conversions": float(pot.conversions) if pot.conversions else None,
                "dismissed": bool(rec.dismissed),
                "details": json.dumps(
                    {
                        "type": enum_name(rec.type_),
                        "resource_name": rec.resource_name,
                    }
                ),
            }
        )
    return out
