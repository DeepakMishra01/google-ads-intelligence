"""User + access-control tables (Google sign-in, roles, per-account grants).

- ``User``: an authenticated team member. Identity comes from Google (``google_sub``
  + ``email``); ``role`` is ``admin`` (full access) or ``manager`` (scoped to the
  accounts granted in ``user_accounts``).
- ``UserAccount``: which Google Ads accounts a manager may see. Admins ignore this
  table (they see everything).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    # Legacy values kept so older rows validate; not assigned by Google sign-in.
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(IntPKMixin, TimestampMixin, Base):
    """An internal platform user (Ads Operations team member)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.MANAGER.value)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Google identity (OpenID Connect ``sub`` — stable per Google account).
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    picture: Mapped[str | None] = mapped_column(String(1024))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserAccount(IntPKMixin, TimestampMixin, Base):
    """Grants one manager access to one Google Ads account."""

    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "account_id", name="user_accounts_user_account"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
