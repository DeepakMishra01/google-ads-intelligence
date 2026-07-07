"""Exception taxonomy for the Google Ads integration layer."""

from __future__ import annotations


class GoogleAdsSyncError(Exception):
    """Base class for all errors raised by the Google Ads integration layer."""


class GoogleAdsAuthError(GoogleAdsSyncError):
    """Credentials are missing, invalid, or the OAuth token could not refresh.

    Not retryable - requires human intervention (rotate token / fix config).
    """


class TransientGoogleAdsError(GoogleAdsSyncError):
    """A temporary failure (5xx, deadline, unavailable). Safe to retry."""


class QuotaExceededError(TransientGoogleAdsError):
    """API quota / rate limit hit. Retryable after a backoff (see retry_after)."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
