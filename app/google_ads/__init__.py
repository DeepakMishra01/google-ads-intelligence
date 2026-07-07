"""Google Ads API integration layer.

Everything that talks to Google's servers lives here and returns plain Python
dicts. Nothing in this package imports the ORM - the service layer maps the
returned dicts onto models. This keeps the API client swappable and testable.
"""

from app.google_ads.client import GoogleAdsClientFactory, get_client_factory
from app.google_ads.exceptions import (
    GoogleAdsAuthError,
    GoogleAdsSyncError,
    QuotaExceededError,
    TransientGoogleAdsError,
)

__all__ = [
    "GoogleAdsClientFactory",
    "get_client_factory",
    "GoogleAdsSyncError",
    "GoogleAdsAuthError",
    "QuotaExceededError",
    "TransientGoogleAdsError",
]
