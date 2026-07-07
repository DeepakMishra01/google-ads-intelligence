"""Recommendation snapshots.

Google Ads recommendations are inherently point-in-time: they appear and
disappear as the system re-evaluates accounts. Each sync captures the currently
active recommendations as an append-only snapshot so history is preserved.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import IntPKMixin, SnapshotMixin


class RecommendationSnapshot(IntPKMixin, SnapshotMixin, Base):
    """An active recommendation captured at sync time (append-only)."""

    __tablename__ = "recommendations"

    resource_name: Mapped[str] = mapped_column(String(512), index=True)
    recommendation_type: Mapped[str | None] = mapped_column(String(64), index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True
    )
    campaign_google_id: Mapped[int | None] = mapped_column(BigInteger)

    # Estimated impact fields (populated when the recommendation type provides them).
    impact_base_cost_micros: Mapped[int | None] = mapped_column(BigInteger)
    impact_potential_cost_micros: Mapped[int | None] = mapped_column(BigInteger)
    impact_base_clicks: Mapped[float | None]
    impact_potential_clicks: Mapped[float | None]
    impact_base_conversions: Mapped[float | None]
    impact_potential_conversions: Mapped[float | None]

    dismissed: Mapped[bool | None]
    # Full raw payload for the recommendation, for Phase 2 analysis.
    details: Mapped[str | None] = mapped_column(Text)
