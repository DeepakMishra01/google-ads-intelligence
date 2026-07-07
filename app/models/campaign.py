"""Campaign dimension + campaign performance snapshot tables (incl. device/geo)."""

from __future__ import annotations

from datetime import date as date_type
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, MetricsMixin, SnapshotMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.ad_group import AdGroup


class Campaign(IntPKMixin, TimestampMixin, Base):
    """Current known configuration of a campaign (upserted by natural key)."""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("account_id", "campaign_id", name="campaigns_account_campaign"),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Google id

    name: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str | None] = mapped_column(String(32))
    serving_status: Mapped[str | None] = mapped_column(String(32))
    advertising_channel_type: Mapped[str | None] = mapped_column(String(32))
    advertising_channel_sub_type: Mapped[str | None] = mapped_column(String(64))
    bidding_strategy_type: Mapped[str | None] = mapped_column(String(64))
    networks: Mapped[str | None] = mapped_column(String(255))  # comma-joined enum list
    start_date: Mapped[date_type | None]
    end_date: Mapped[date_type | None]
    optimization_score: Mapped[float | None]
    budget_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    account: Mapped[Account] = relationship(back_populates="campaigns")
    ad_groups: Mapped[list[AdGroup]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list[CampaignSnapshot]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only daily performance + config snapshot for a campaign."""

    __tablename__ = "campaign_snapshots"

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    # Config captured alongside metrics so history reflects what was live that day.
    status: Mapped[str | None] = mapped_column(String(32))
    budget_micros: Mapped[int | None] = mapped_column(BigInteger)
    bidding_strategy_type: Mapped[str | None] = mapped_column(String(64))
    optimization_score: Mapped[float | None]

    campaign: Mapped[Campaign] = relationship(back_populates="snapshots")


class CampaignDeviceSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only per-device performance snapshot for a campaign."""

    __tablename__ = "campaign_device_snapshots"

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    device: Mapped[str] = mapped_column(String(32), index=True)  # MOBILE/DESKTOP/TABLET


class CampaignGeoSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only per-geo (country/region) performance snapshot for a campaign."""

    __tablename__ = "campaign_geo_snapshots"

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    country_criterion_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    location_name: Mapped[str | None] = mapped_column(String(255))
