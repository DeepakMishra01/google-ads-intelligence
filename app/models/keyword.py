"""Keyword dimension + keyword snapshot tables (includes Quality Score history)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, MetricsMixin, SnapshotMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ad_group import AdGroup


class Keyword(IntPKMixin, TimestampMixin, Base):
    """Current known configuration of an ad-group keyword criterion."""

    __tablename__ = "keywords"
    __table_args__ = (
        UniqueConstraint("ad_group_id", "criterion_id", name="keywords_adgroup_criterion"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Google id

    text: Mapped[str | None] = mapped_column(String(1024), index=True)
    match_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    cpc_bid_micros: Mapped[int | None] = mapped_column(BigInteger)

    snapshots: Mapped[list[KeywordSnapshot]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )
    ad_group: Mapped[AdGroup] = relationship(back_populates="keywords")


class KeywordSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only daily snapshot for a keyword, including Quality Score history."""

    __tablename__ = "keyword_snapshots"

    keyword_id: Mapped[int] = mapped_column(
        ForeignKey("keywords.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )

    match_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))

    # Quality Score and its three sub-components (as strings from the API enum,
    # e.g. ABOVE_AVERAGE / AVERAGE / BELOW_AVERAGE).
    quality_score: Mapped[int | None] = mapped_column(Integer)
    expected_ctr: Mapped[str | None] = mapped_column(String(32))
    landing_page_experience: Mapped[str | None] = mapped_column(String(32))
    ad_relevance: Mapped[str | None] = mapped_column(String(32))

    keyword: Mapped[Keyword] = relationship(back_populates="snapshots")
