"""FastAPI application factory and process entrypoint.

Run locally:  uvicorn app.main:app --reload
In Docker:    handled by the container entrypoint (migrations then uvicorn).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.tasks.scheduler import shutdown_scheduler, start_scheduler

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    """Start the scheduler on boot; stop it on shutdown."""
    configure_logging()
    settings = get_settings()
    log.info("app.startup", env=settings.app_env, version=__version__)
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Google Ads Intelligence Layer",
        version=__version__,
        description=(
            "Phase 1 data collection platform. Continuously syncs Google Ads data "
            "into PostgreSQL as append-only historical snapshots and exposes REST + "
            "dashboard APIs for the Ads Operations team and future AI agents."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS is permissive by default for an internal tool; tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", tags=["root"], summary="Service metadata")
    def root() -> dict:
        return {
            "service": "google-ads-intelligence",
            "version": __version__,
            "docs": "/docs",
            "api_prefix": settings.api_prefix,
        }

    return app


app = create_app()
