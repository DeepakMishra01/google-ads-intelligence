"""Structured logging setup built on structlog.

Call `configure_logging()` once at process startup. Everywhere else use
`get_logger(__name__)` and log with key/value pairs, e.g.:

    log = get_logger(__name__)
    log.info("sync.started", account_id=cid, entity="campaigns")
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config.settings import get_settings

_configured = False


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Idempotent."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.app_log_level, logging.INFO)

    # Route stdlib logging (uvicorn, sqlalchemy, google-ads) through stdout.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_log_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=not settings.is_production)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Tame noisy third-party loggers.
    for noisy in ("google.ads.googleads.client", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING if not settings.db_echo else logging.INFO)

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, configuring logging on first use."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
