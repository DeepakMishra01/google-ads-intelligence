"""AI Ad Copy Generator — generation-history table.

One append-style row per generation run. The rich, variable-shape outputs
(assets, scores, reasoning, the historical features fed to the model) are stored
as JSONB so the schema stays stable as the engine evolves. Mirrors the JSONType
pattern from ``sync_log.py`` / ``alert.py``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text
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
    # User edits to the keyword set: {"added": [{keyword, search_volume, ...}],
    # "removed": ["kw", ...]}. The approval plan/email reflect these with tags.
    keyword_edits: Mapped[dict | None] = mapped_column(JSONType)
    generated_assets: Mapped[dict | None] = mapped_column(JSONType)
    # Ad-manager edits to the generated ad copy: {"headlines": [str, ...],
    # "descriptions": [str, ...], "callouts": [str, ...], "by": email, "at": iso}.
    # Each list is the FULL desired set (edits + additions); anything not present in
    # the original generated_assets is flagged "edited by the ad manager" in the
    # approval plan / email / Excel.
    asset_edits: Mapped[dict | None] = mapped_column(JSONType)
    # Full generate() result payload (JSON-safe) so a saved plan can be re-opened in
    # the UI exactly as generated — after the user navigates away, switches tools, or
    # reloads. This is what makes generations persistent "records" on the platform.
    result_payload: Mapped[dict | None] = mapped_column(JSONType)
    scores: Mapped[dict | None] = mapped_column(JSONType)
    reasoning: Mapped[dict | None] = mapped_column(JSONType)

    # --- Accountability / approval workflow ---
    # draft -> submitted -> approved | rejected. A campaign is "cleared to launch"
    # only when approved. Never physically blocks Google — it's the approval record.
    approval_status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewer_name: Mapped[str | None] = mapped_column(String(160))
    review_note: Mapped[str | None] = mapped_column(Text)
    # Operator overrides of auto-generated strategy values: {field: {auto, manual, by, at}}.
    overrides: Mapped[dict | None] = mapped_column(JSONType)
    # Unguessable token backing the one-click Approve/Reject links in the email.
    approval_token: Mapped[str | None] = mapped_column(String(64), index=True)
    # The ad manager who owns this campaign (for per-manager performance rollups).
    ad_manager: Mapped[str | None] = mapped_column(String(160), index=True)
    # Signed-in owner (drives access control): the AM assigned this campaign in the
    # Accountability tab. Their account scope includes this generation's account_id.
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Who clicked "Submit for approval" — emailed the reviewer's decision.
    submitter_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )


class ApprovalEvent(IntPKMixin, TimestampMixin, Base):
    """Append-only audit trail of approval actions on a generation."""

    __tablename__ = "approval_events"

    generation_id: Mapped[int] = mapped_column(
        ForeignKey("ad_copy_generations.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(String(24))  # submitted | approved | rejected | edited
    actor: Mapped[str | None] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(Text)


class ScorecardSnapshot(IntPKMixin, TimestampMixin, Base):
    """A saved weekly scorecard for a campus (objective vs expected vs achieved).

    Persisted on demand or by the weekly job so results can be tracked
    week-over-week and each report compares against the previous one. The full
    computed payload is kept in ``payload``; a few metrics are also columns so
    trend queries stay cheap.
    """

    __tablename__ = "scorecard_snapshots"

    campus: Mapped[str] = mapped_column(String(255), index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("ad_copy_generations.id", ondelete="SET NULL"), nullable=True
    )

    # Indexed trend metrics (nullable — a fresh plan may have no results yet).
    achieved_leads: Mapped[float | None] = mapped_column(Numeric(16, 2))
    achieved_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    achieved_clicks: Mapped[int | None] = mapped_column()
    implementation_pct: Mapped[int | None] = mapped_column()
    expected_leads: Mapped[float | None] = mapped_column(Numeric(16, 2))
    target_leads: Mapped[int | None] = mapped_column()

    payload: Mapped[dict | None] = mapped_column(JSONType)
