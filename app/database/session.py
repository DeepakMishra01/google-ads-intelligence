"""Engine, session factory, and FastAPI/worker session helpers."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_settings = get_settings()

# A single shared engine per process. `pool_pre_ping` recycles dead connections
# (important for long-lived scheduler processes hitting a remote Postgres).
engine = create_engine(
    _settings.sqlalchemy_database_uri,
    echo=_settings.db_echo,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session.

    The session is read-mostly for API endpoints; commits are the caller's
    responsibility (services). Always closed on request teardown.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context for background jobs / scripts.

    Commits on success, rolls back on exception, always closes. Use this in the
    sync engine and any non-request code path.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
