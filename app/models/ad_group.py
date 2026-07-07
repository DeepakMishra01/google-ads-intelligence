"""Ad group dimension + ad group performance snapshot tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, MetricsMixin, SnapshotMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ad import Ad
    from app.models.campaign import Campaign
    from app.models.keyword import Keyword


class AdGroup(IntPKMixin, TimestampMixin, Base):
    """Current known configuration of an ad group (upserted by natural key)."""

    __tablename__ = "ad_groups"
    __table_args__ = (
        UniqueConstraint("campaign_id", "ad_group_id", name="ad_groups_campaign_adgroup"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Google id

    name: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str | None] = mapped_column(String(32))
    type: Mapped[str | None] = mapped_column(String(64))
    cpc_bid_micros: Mapped[int | None] = mapped_column(BigInteger)

    campaign: Mapped[Campaign] = relationship(back_populates="ad_groups")
    keywords: Mapped[list[Keyword]] = relationship(
        back_populates="ad_group", cascade="all, delete-orphan"
    )
    ads: Mapped[list[Ad]] = relationship(back_populates="ad_group", cascade="all, delete-orphan")
    snapshots: Mapped[list[AdGroupSnapshot]] = relationship(
        back_populates="ad_group", cascade="all, delete-orphan"
    )


class AdGroupSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only daily performance + config snapshot for an ad group."""

    __tablename__ = "ad_group_snapshots"

    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str | None] = mapped_column(String(32))
    cpc_bid_micros: Mapped[int | None] = mapped_column(BigInteger)

    ad_group: Mapped[AdGroup] = relationship(back_populates="snapshots")
