"""Search term dimension + search term snapshot tables.

Search terms are the actual user queries that triggered ads. The dimension row
is the distinct (ad_group, query, match_type) tuple; the snapshot carries the
daily metrics for that query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import IntPKMixin, MetricsMixin, SnapshotMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.ad_group import AdGroup


class SearchTerm(IntPKMixin, TimestampMixin, Base):
    """A distinct search query observed for an ad group."""

    __tablename__ = "search_terms"
    __table_args__ = (
        UniqueConstraint(
            "ad_group_id", "query", "match_type", name="search_terms_adgroup_query_match"
        ),
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )

    query: Mapped[str] = mapped_column(String(1024), index=True)
    match_type: Mapped[str | None] = mapped_column(String(32))
    # Status of the query: NONE / ADDED / EXCLUDED / ADDED_EXCLUDED.
    search_term_targeting_status: Mapped[str | None] = mapped_column(String(32))

    ad_group: Mapped[AdGroup] = relationship()
    snapshots: Mapped[list[SearchTermSnapshot]] = relationship(
        back_populates="search_term", cascade="all, delete-orphan"
    )


class SearchTermSnapshot(IntPKMixin, SnapshotMixin, MetricsMixin, Base):
    """Append-only daily performance snapshot for a search query."""

    __tablename__ = "search_term_snapshots"

    search_term_id: Mapped[int] = mapped_column(
        ForeignKey("search_terms.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[int] = mapped_column(
        ForeignKey("ad_groups.id", ondelete="CASCADE"), index=True
    )

    search_term: Mapped[SearchTerm] = relationship(back_populates="snapshots")
