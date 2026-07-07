"""Account discovery under the manager (MCC) account."""

from __future__ import annotations

from typing import Any

from app.google_ads.client import GoogleAdsClientFactory
from app.google_ads.reports._helpers import enum_name

# customer_client.level 0 = the manager itself, 1 = direct child accounts.
GAQL_ACCOUNTS = """
SELECT
  customer_client.id,
  customer_client.descriptive_name,
  customer_client.currency_code,
  customer_client.time_zone,
  customer_client.manager,
  customer_client.test_account,
  customer_client.status,
  customer_client.level
FROM customer_client
WHERE customer_client.level <= 1
""".strip()


def fetch_accounts(
    factory: GoogleAdsClientFactory, manager_customer_id: str
) -> list[dict[str, Any]]:
    """Return all accounts (the MCC + its direct children)."""
    rows = factory.search(manager_customer_id, GAQL_ACCOUNTS)
    out: list[dict[str, Any]] = []
    for r in rows:
        cc = r.customer_client
        out.append(
            {
                "customer_id": str(cc.id),
                "descriptive_name": cc.descriptive_name or None,
                "currency_code": cc.currency_code or None,
                "time_zone": cc.time_zone or None,
                "is_manager": bool(cc.manager),
                "test_account": bool(cc.test_account),
                "status": enum_name(cc.status),
                "manager_customer_id": manager_customer_id,
            }
        )
    return out
