"""Anthropic (Claude) LLM client: cached, retry-wrapped, typed errors.

Modeled on :class:`app.google_ads.client.GoogleAdsClientFactory`. The rest of the
codebase depends only on the small :meth:`LLMClient.complete` surface, so a
different provider can be swapped behind it later without touching callers.

The client is intentionally forgiving: if the ``anthropic`` package or the API
key is missing, :meth:`available` returns ``False`` and callers fall back to the
deterministic generator — the AI Ad Copy module must never hard-fail on config.
"""

from __future__ import annotations

from functools import lru_cache

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai_clients.exceptions import (
    LLMNotConfiguredError,
    LLMResponseError,
    LLMTransientError,
)
from app.config.logging import get_logger
from app.config.settings import Settings, get_settings

log = get_logger(__name__)


class LLMClient:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None  # lazily constructed anthropic.Anthropic

    # ------------------------------------------------------------------ #
    # Availability / construction
    # ------------------------------------------------------------------ #
    def available(self) -> bool:
        """True when the LLM backend can be used (enabled + key + package)."""
        s = self._settings
        if not (s.ad_copy_llm_enabled and s.anthropic_api_key):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is not None:
            return self._client
        s = self._settings
        if not (s.ad_copy_llm_enabled and s.anthropic_api_key):
            raise LLMNotConfiguredError("ANTHROPIC_API_KEY not set or LLM disabled.")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise LLMNotConfiguredError(
                "anthropic package not installed; run `pip install anthropic`."
            ) from exc
        self._client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        return self._client

    # ------------------------------------------------------------------ #
    # Completion
    # ------------------------------------------------------------------ #
    def complete(self, *, system: str, prompt: str, max_tokens: int | None = None) -> str:
        """Return the model's text response. Raises on transient/response errors."""
        return self._retry_decorator()(self._complete_once)(system, prompt, max_tokens)

    def _retry_decorator(self):  # type: ignore[no-untyped-def]
        s = self._settings
        return retry(
            retry=retry_if_exception_type(LLMTransientError),
            stop=stop_after_attempt(max(1, s.sync_max_retries)),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            reraise=True,
        )

    def _complete_once(self, system: str, prompt: str, max_tokens: int | None) -> str:
        client = self._get_client()
        s = self._settings
        try:
            msg = client.messages.create(
                model=s.ad_copy_llm_model,
                max_tokens=max_tokens or s.ad_copy_llm_max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # translate SDK/transport errors
            self._raise_translated(exc)
        parts = [b.text for b in getattr(msg, "content", []) if getattr(b, "type", "") == "text"]
        text = "\n".join(parts).strip()
        if not text:
            raise LLMResponseError("Empty response from model.")
        log.debug("llm.complete.ok", model=s.ad_copy_llm_model, chars=len(text))
        return text

    def _raise_translated(self, exc: Exception) -> None:
        """Map anthropic SDK errors onto the retryable/fatal taxonomy."""
        try:
            import anthropic

            transient = (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
                anthropic.InternalServerError,
            )
            if isinstance(exc, transient):
                raise LLMTransientError(str(exc)) from exc
        except ImportError:  # pragma: no cover
            pass
        raise LLMResponseError(str(exc)) from exc


@lru_cache
def get_llm_client() -> LLMClient:
    """Process-wide cached LLM client (dependency-injection seam)."""
    return LLMClient()
