"""FastAPI application factory and process entrypoint.

Run locally:  uvicorn app.main:app --reload
In Docker:    handled by the container entrypoint (migrations then uvicorn).
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.database.session import session_scope
from app.repositories.audit_log import AuditLogRepository
from app.tasks.scheduler import shutdown_scheduler, start_scheduler

log = get_logger(__name__)

# Methods that mutate state are always audited (Module 13).
_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _record_audit(request: Request, status_code: int, duration_ms: int) -> None:
    """Best-effort audit write; never breaks the request on failure."""
    try:
        with session_scope() as db:
            AuditLogRepository(db).record(
                actor=request.headers.get("X-Actor"),
                role=(request.headers.get("X-Role") or "").lower() or None,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else None,
            )
    except Exception as exc:  # noqa: BLE001 - auditing must not affect responses
        log.warning("audit.write_failed", error=str(exc))


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

    # Compress JSON/report payloads over ~500 bytes (tables, trends, exports).
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS is permissive by default for an internal tool; tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next):  # noqa: ANN001,ANN202
        start = time.monotonic()
        response = await call_next(request)
        if settings.audit_enabled and request.method in _AUDITED_METHODS:
            _record_audit(
                request, response.status_code, int((time.monotonic() - start) * 1000)
            )
        return response

    app.include_router(api_router, prefix=settings.api_prefix)

    # Service metadata (stable JSON contract, independent of whether the UI is built).
    @app.get(f"{settings.api_prefix}/meta", tags=["root"], summary="Service metadata")
    def meta() -> dict:
        return {
            "service": "google-ads-intelligence",
            "version": __version__,
            "docs": "/docs",
            "api_prefix": settings.api_prefix,
        }

    _mount_frontend(app, settings.api_prefix)
    return app


def _mount_frontend(app: FastAPI, api_prefix: str) -> None:
    """Serve the built React app from FastAPI so the whole product is ONE process.

    When ``frontend/dist`` exists (``npm run build``), static assets are served and
    any non-API/deep-link route falls back to ``index.html`` for client-side routing.
    When it doesn't (dev/tests), the root returns the service metadata instead — so
    nothing here depends on a separate Vite dev server that can crash.
    """
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    index = dist / "index.html"

    if not index.exists():
        @app.get("/", tags=["root"], summary="Service metadata")
        def root() -> dict:
            return {
                "service": "google-ads-intelligence",
                "docs": "/docs",
                "api_prefix": api_prefix,
                "ui": "not built — run `npm --prefix frontend run build`",
            }
        return

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    # Reserved prefixes that must never be shadowed by the SPA fallback.
    reserved = (api_prefix.strip("/"), "docs", "redoc", "openapi.json", "assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.split("/", 1)[0] in reserved:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)  # SPA client-side route → index.html


app = create_app()
