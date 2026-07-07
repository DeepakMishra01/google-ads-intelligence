"""Google Ads client factory guards (no network calls)."""

from __future__ import annotations

import pytest

from app.config.settings import get_settings
from app.google_ads.client import GoogleAdsClientFactory
from app.google_ads.exceptions import GoogleAdsAuthError


def test_missing_credentials_raise_auth_error():
    settings = get_settings()
    settings.google_ads_developer_token = ""
    settings.google_ads_refresh_token = ""
    factory = GoogleAdsClientFactory(settings=settings)
    with pytest.raises(GoogleAdsAuthError):
        factory.get_client()


def test_login_customer_id_validator_strips_dashes():
    from app.config.settings import Settings

    settings = Settings(google_ads_login_customer_id="123-456-7890")
    assert settings.google_ads_login_customer_id == "1234567890"


def test_client_customer_id_list_parsing():
    from app.config.settings import Settings

    settings = Settings(google_ads_client_customer_ids="111-111-1111, 2222222222")
    assert settings.client_customer_id_list == ["1111111111", "2222222222"]
