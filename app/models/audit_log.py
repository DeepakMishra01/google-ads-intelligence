"""Audit / request log - lightweight accountability trail (Module 13).

Every mutating or privileged request is recorded here by the audit middleware.
Read requests can optionally be logged too. This is deliberately simple; it gives
Phase 3 a hook for richer RBAC and per-actor attribution without a schema change.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin


class AuditLog(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor: Mapped[str | None] = mapped_column(String(320), index=True)  # email/user id
    role: Mapped[str | None] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(512), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)
