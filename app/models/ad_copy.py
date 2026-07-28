"""AI Ad Copy Generator — generation-history table.

One append-style row per generation run. The rich, variable-shape outputs
(assets, scores, reasoning, the historical features fed to the model) are stored
as JSONB so the schema stays stable as the engine evolves. Mirrors the JSONType
pattern from ``sync_log.py`` / ``alert.py``.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, TimestampMixin

# JSONB on Postgres (indexable, efficient); plain JSON on SQLite for tests.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class AdCopyGeneration(IntPKMixin, TimestampMixin, Base):
    """A single AI Ad Copy generation run and its full result."""

    __tablename__ = "ad_copy_generations"

    # Who / what this generation was for.
    actor: Mapped[str | None] = mapped_column(String(320), index=True)  # X-Actor header
    campus: Mapped[str] = mapped_column(String(255), index=True)
    # Optional links back into the warehouse (a campus can span accounts/campaigns).
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Final-URL discovery result.
    final_url: Mapped[str | None] = mapped_column(Text)
    url_source: Mapped[str | None] = mapped_column(String(48))  # e.g. "historical_ads"
    url_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))

    # Which engine produced the copy ("llm" or "template").
    backend: Mapped[str | None] = mapped_column(String(16))

    # Variable-shape payloads.
    historical_features_used: Mapped[dict | None] = mapped_column(JSONType)
    keyword_snapshot: Mapped[dict | None] = mapped_column(JSONType)
    generated_assets: Mapped[dict | None] = mapped_column(JSONType)
    scores: Mapped[dict | None] = mapped_column(JSONType)
    reasoning: Mapped[dict | None] = mapped_column(JSONType)
