"""OAuth token storage for future multi-tenant credential management.

Phase 1 reads Google Ads credentials from environment variables. This table
exists so Phase 2 can manage per-account OAuth grants (e.g. onboarding a college
that authorizes access to its own account) without schema changes.

SECURITY: refresh tokens must be encrypted at rest before this table is used in
production. The column is named ``refresh_token_encrypted`` to make that
requirement explicit; the encryption layer is intentionally left for Phase 2.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin


class ApiToken(IntPKMixin, TimestampMixin, Base):
    """A stored OAuth credential grant for a provider/account."""

    __tablename__ = "api_tokens"

    provider: Mapped[str] = mapped_column(String(32), default="google_ads", index=True)
    # Optional link to the account this token authorizes.
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str | None] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None]
    is_active: Mapped[bool] = mapped_column(default=True)
