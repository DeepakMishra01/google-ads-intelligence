"""Recommendation fetcher (Google Ads API v24 compatible).

Recommendations are point-in-time optimization suggestions. The estimated-impact
sub-fields were removed from the API, so we capture identity + type only; the
impact_* keys are kept (as None) to preserve the service contract.
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
  campaign.id
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
        campaign_gid = int(r.campaign.id) if r.campaign.id else None
        out.append(
            {
                "resource_name": rec.resource_name,
                "recommendation_type": enum_name(rec.type_),
                "campaign_google_id": campaign_gid,
                "impact_base_cost_micros": None,
                "impact_potential_cost_micros": None,
                "impact_base_clicks": None,
                "impact_potential_clicks": None,
                "impact_base_conversions": None,
                "impact_potential_conversions": None,
                "dismissed": bool(rec.dismissed),
                "details": json.dumps(
                    {"type": enum_name(rec.type_), "resource_name": rec.resource_name}
                ),
            }
        )
    return out
