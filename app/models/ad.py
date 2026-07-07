"""Ad dimension + ad snapshot tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, MetricsMixin, SnapshotMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ad_group import AdGroup


class Ad(IntPKMixin, TimestampMixin, Base):
    """Current known configuration of an ad within an ad group."""

    __tablename__ = "ads"
    __table_args__ = (UniqueConstraint("ad_group_id", "ad_id", name="ads_adgroup_ad"),)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    ad_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Google id

    type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    approval_status: Mapped[str | None] = mapped_column(String(32))
    final_urls: Mapped[str | None] = mapped_column(Text)  # newline-joined
    # Responsive Search Ad assets stored as newline-joined text for readability.
    headlines: Mapped[str | None] = mapped_column(Text)
    descriptions: Mapped[str | None] = mapped_column(Text)

    ad_group: Mapped[AdGroup] = relationship(back_populates="ads")
    snapshots: Mapped[list[AdSnapshot]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )


class AdSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only daily performance + status snapshot for an ad."""

    __tablename__ = "ad_snapshots"

    ad_id: Mapped[int] = mapped_column(ForeignKey("ads.id", ondelete="CASCADE"), index=True)
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str | None] = mapped_column(String(32))
    approval_status: Mapped[str | None] = mapped_column(String(32))

    ad: Mapped[Ad] = relationship(back_populates="snapshots")
