"""Health / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness + DB readiness probe")
def health(db: Session = Depends(get_db)) -> dict:
    """Return service liveness and database connectivity."""
    db_ok = True
    db_error: str | None = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "database": {"connected": db_ok, "error": db_error},
    }


@router.get("/health/live", summary="Liveness only (no dependencies)")
def live() -> dict:
    return {"status": "ok"}
