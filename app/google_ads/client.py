"""Google Ads API client factory, query execution, retry and quota handling.

The official ``google-ads`` library is synchronous and thread-safe once built,
so we cache a single ``GoogleAdsClient`` per process and reuse it across all
customer ids (the login/manager customer id is fixed; the per-request customer
id is passed to each ``search`` call).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.google_ads.exceptions import (
    GoogleAdsAuthError,
    QuotaExceededError,
    TransientGoogleAdsError,
)

if TYPE_CHECKING:  # avoid importing the heavy SDK unless it is actually installed
    from google.ads.googleads.client import GoogleAdsClient

log = get_logger(__name__)

# Google Ads error codes that indicate a transient / retryable condition.
_RETRYABLE_QUOTA_CODES = {"RESOURCE_EXHAUSTED", "RESOURCE_TEMPORARILY_EXHAUSTED"}


class GoogleAdsClientFactory:
    """Builds and caches a GoogleAdsClient and runs GAQL queries with retries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: GoogleAdsClient | None = None

    # ------------------------------------------------------------------ #
    # Client construction
    # ------------------------------------------------------------------ #
    @property
    def _config_dict(self) -> dict[str, Any]:
        s = self._settings
        cfg: dict[str, Any] = {
            "developer_token": s.google_ads_developer_token,
            "client_id": s.google_ads_client_id,
            "client_secret": s.google_ads_client_secret,
            "refresh_token": s.google_ads_refresh_token,
            "use_proto_plus": True,
        }
        if s.google_ads_login_customer_id:
            cfg["login_customer_id"] = s.google_ads_login_customer_id
        return cfg

    def get_client(self) -> GoogleAdsClient:
        """Lazily build (and cache) the underlying GoogleAdsClient."""
        if self._client is not None:
            return self._client

        s = self._settings
        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise GoogleAdsAuthError(
                "google-ads library not installed; run `pip install google-ads`."
            ) from exc

        if not s.google_ads_developer_token or not s.google_ads_refresh_token:
            raise GoogleAdsAuthError(
                "Google Ads credentials are not configured. Set GOOGLE_ADS_* env vars "
                "or GOOGLE_ADS_YAML_PATH."
            )

        try:
            version = s.google_ads_api_version or None
            if s.google_ads_yaml_path:
                self._client = GoogleAdsClient.load_from_storage(
                    path=s.google_ads_yaml_path, version=version
                )
            else:
                self._client = GoogleAdsClient.load_from_dict(self._config_dict, version=version)
        except Exception as exc:  # pragma: no cover - construction failure
            raise GoogleAdsAuthError(f"Failed to build GoogleAdsClient: {exc}") from exc

        return self._client

    # ------------------------------------------------------------------ #
    # Query execution
    # ------------------------------------------------------------------ #
    def search(self, customer_id: str, query: str) -> list[Any]:
        """Run a GAQL query for a customer id and return all rows.

        Uses ``search_stream`` which paginates transparently server-side. The
        whole result set is materialized within the retry boundary so a
        transient mid-stream failure re-runs the entire query cleanly.
        """
        customer_id = customer_id.replace("-", "").strip()
        return self._search_with_retry(customer_id, query)

    def _retry_decorator(self):  # type: ignore[no-untyped-def]
        s = self._settings
        return retry(
            retry=retry_if_exception_type(TransientGoogleAdsError),
            stop=stop_after_attempt(max(1, s.sync_max_retries)),
            wait=wait_exponential(multiplier=s.sync_retry_backoff_seconds, min=1, max=300),
            reraise=True,
        )

    def _search_with_retry(self, customer_id: str, query: str) -> list[Any]:
        # Bind the retry policy from settings at call time.
        return self._retry_decorator()(self._search_once)(customer_id, query)

    def _search_once(self, customer_id: str, query: str) -> list[Any]:
        client = self.get_client()
        ga_service = client.get_service("GoogleAdsService")
        rows: list[Any] = []
        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            for batch in stream:
                rows.extend(batch.results)
        except Exception as exc:  # translate SDK errors into our taxonomy
            self._raise_translated(exc, customer_id)
        log.debug("google_ads.search.ok", customer_id=customer_id, rows=len(rows))
        return rows

    def list_accessible_customers(self) -> list[str]:
        """Return customer ids (digits) the authenticated user can access."""
        client = self.get_client()
        service = client.get_service("CustomerService")
        try:
            response = service.list_accessible_customers()
        except Exception as exc:
            self._raise_translated(exc, self._settings.google_ads_login_customer_id)
        # resource_names look like "customers/1234567890".
        return [rn.split("/")[-1] for rn in response.resource_names]

    # ------------------------------------------------------------------ #
    # Error translation
    # ------------------------------------------------------------------ #
    def _raise_translated(self, exc: Exception, customer_id: str | None) -> None:
        """Map an SDK/transport exception onto our retryable/fatal taxonomy."""
        # Google Ads API application-level failures.
        try:
            from google.ads.googleads.errors import GoogleAdsException
        except ImportError:  # pragma: no cover
            GoogleAdsException = ()  # type: ignore[assignment]  # noqa: N806

        if GoogleAdsException and isinstance(exc, GoogleAdsException):
            codes: list[str] = []
            for error in exc.failure.errors:
                # Auth failures -> fatal.
                if error.error_code.authentication_error or error.error_code.authorization_error:
                    raise GoogleAdsAuthError(
                        f"Auth error for customer {customer_id}: {error.message}"
                    ) from exc
                if error.error_code.quota_error:
                    raise QuotaExceededError(
                        f"Quota error for customer {customer_id}: {error.message}"
                    ) from exc
                codes.append(str(error.error_code))
            # Any other GoogleAdsException is treated as fatal for this entity.
            raise TransientGoogleAdsError(
                f"Google Ads request failed for {customer_id}: {codes}"
            ) from exc

        # Transport-level (gRPC) errors from google.api_core.
        try:
            from google.api_core import exceptions as gexc

            transient = (
                gexc.ServiceUnavailable,
                gexc.DeadlineExceeded,
                gexc.InternalServerError,
                gexc.TooManyRequests,
                gexc.ResourceExhausted,
            )
            if isinstance(exc, gexc.ResourceExhausted | gexc.TooManyRequests):
                raise QuotaExceededError(f"Rate limited for {customer_id}: {exc}") from exc
            if isinstance(exc, transient):
                raise TransientGoogleAdsError(str(exc)) from exc
        except ImportError:  # pragma: no cover
            pass

        # Unknown -> re-raise so it surfaces loudly.
        raise exc

    def search_iter(self, customer_id: str, query: str) -> Iterator[Any]:
        """Convenience iterator over :meth:`search` results."""
        yield from self.search(customer_id, query)


@lru_cache
def get_client_factory() -> GoogleAdsClientFactory:
    """Process-wide cached factory (dependency-injection seam)."""
    return GoogleAdsClientFactory()
