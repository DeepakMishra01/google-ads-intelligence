"""Typed exceptions for the LLM client (mirrors app/google_ads/exceptions.py)."""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM client failures."""


class LLMNotConfiguredError(LLMError):
    """No API key / provider configured — caller should use a fallback."""


class LLMTransientError(LLMError):
    """Retryable failure (timeout, rate limit, 5xx)."""


class LLMResponseError(LLMError):
    """The model returned an unusable / unparseable response."""
