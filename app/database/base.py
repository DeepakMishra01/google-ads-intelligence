"""SQLAlchemy declarative base with a consistent constraint naming convention.

A deterministic naming convention is required for Alembic to emit stable,
reversible migrations (especially for dropping constraints by name).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic names for indexes/constraints -> clean Alembic autogenerate.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Ensure all `datetime` columns are timezone-aware at the DB layer.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }
