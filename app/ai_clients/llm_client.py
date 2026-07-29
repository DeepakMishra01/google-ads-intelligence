"""LLM client with pluggable providers: Anthropic (Claude) and Google (Gemini).

The rest of the codebase depends only on :meth:`LLMClient.complete`, so the
provider is chosen here from configuration:

  * ``ad_copy_llm_provider = "auto"`` (default): Anthropic if its key is set,
    else Gemini if its key is set, else no LLM (deterministic fallback).
  * ``"anthropic"`` / ``"gemini"``: force one provider.

Gemini is intended for testing; Anthropic for production. Neither is required —
if no key is configured the generator uses its deterministic engine.
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
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._anthropic = None  # cached anthropic.Anthropic
        self._gemini = None  # cached google.generativeai module

    # ------------------------------------------------------------------ #
    # Provider selection
    # ------------------------------------------------------------------ #
    def _anthropic_ready(self) -> bool:
        if not self._settings.anthropic_api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _gemini_ready(self) -> bool:
        if not self._settings.gemini_api_key:
            return False
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return False
        return True

    def provider(self) -> str | None:
        """Return the active provider name, or None to use the deterministic engine."""
        s = self._settings
        if not s.ad_copy_llm_enabled:
            return None
        pref = (s.ad_copy_llm_provider or "auto").lower()
        if pref == "anthropic":
            return "anthropic" if self._anthropic_ready() else None
        if pref == "gemini":
            return "gemini" if self._gemini_ready() else None
        # auto: Anthropic first (production), else Gemini (testing).
        if self._anthropic_ready():
            return "anthropic"
        if self._gemini_ready():
            return "gemini"
        return None

    def available(self) -> bool:
        return self.provider() is not None

    # ------------------------------------------------------------------ #
    # Completion
    # ------------------------------------------------------------------ #
    def complete(self, *, system: str, prompt: str, max_tokens: int | None = None) -> str:
        provider = self.provider()
        if provider is None:
            raise LLMNotConfiguredError("No LLM provider configured (Anthropic/Gemini).")
        return self._retry_decorator()(self._complete_once)(provider, system, prompt, max_tokens)

    def _retry_decorator(self):  # type: ignore[no-untyped-def]
        s = self._settings
        return retry(
            retry=retry_if_exception_type(LLMTransientError),
            stop=stop_after_attempt(max(1, s.sync_max_retries)),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            reraise=True,
        )

    def _complete_once(
        self, provider: str, system: str, prompt: str, max_tokens: int | None
    ) -> str:
        if provider == "anthropic":
            return self._anthropic_complete(system, prompt, max_tokens)
        return self._gemini_complete(system, prompt, max_tokens)

    # ------------------------------ Anthropic -------------------------- #
    def _anthropic_complete(self, system: str, prompt: str, max_tokens: int | None) -> str:
        s = self._settings
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMNotConfiguredError("anthropic package not installed.") from exc
        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=s.anthropic_api_key)
        try:
            msg = self._anthropic.messages.create(
                model=s.ad_copy_llm_model,
                max_tokens=max_tokens or s.ad_copy_llm_max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            self._raise_anthropic(exc)
        parts = [b.text for b in getattr(msg, "content", []) if getattr(b, "type", "") == "text"]
        text = "\n".join(parts).strip()
        if not text:
            raise LLMResponseError("Empty response from Claude.")
        log.debug("llm.complete.ok", provider="anthropic", chars=len(text))
        return text

    def _raise_anthropic(self, exc: Exception) -> None:
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

    # ------------------------------ Gemini ----------------------------- #
    def _gemini_complete(self, system: str, prompt: str, max_tokens: int | None) -> str:
        s = self._settings
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise LLMNotConfiguredError(
                "google-generativeai not installed; run `pip install google-generativeai`."
            ) from exc
        if self._gemini is None:
            genai.configure(api_key=s.gemini_api_key)
            self._gemini = genai
        model = self._gemini.GenerativeModel(s.gemini_model, system_instruction=system)
        try:
            resp = model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": max_tokens or s.ad_copy_llm_max_tokens,
                    "response_mime_type": "application/json",
                },
            )
        except Exception as exc:
            self._raise_gemini(exc)
        try:
            text = (resp.text or "").strip()
        except Exception as exc:  # blocked / no candidates → .text raises
            raise LLMResponseError(f"Gemini returned no usable text: {exc}") from exc
        if not text:
            raise LLMResponseError("Empty response from Gemini.")
        log.debug("llm.complete.ok", provider="gemini", chars=len(text))
        return text

    def _raise_gemini(self, exc: Exception) -> None:
        name = type(exc).__name__.lower()
        transient = ("resourceexhausted", "serviceunavailable", "deadline",
                     "toomany", "ratelimit", "internal", "unavailable")
        if any(k in name for k in transient):
            raise LLMTransientError(str(exc)) from exc
        raise LLMResponseError(str(exc)) from exc


@lru_cache
def get_llm_client() -> LLMClient:
    """Process-wide cached LLM client (dependency-injection seam)."""
    return LLMClient()
