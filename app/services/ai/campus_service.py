"""Campus discovery + Final-URL detection (Steps 1-2).

Campus search returns autocomplete suggestions from curated briefs enriched with
warehouse history. Final-URL discovery ranks historical ad landing pages by real
performance (spend → clicks → CTR); the official homepage is only a low-confidence
fallback when no historical URL exists.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, false, func, not_, or_, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ad import Ad, AdSnapshot
from app.models.campaign import Campaign, CampaignSnapshot
from app.services.ai.campus_config import (
    CAMPUS_BRIEFS,
    CampusBrief,
    find_brief,
    generic_brief,
)

_MICROS = 1_000_000


def campus_campaign_filter(brief: CampusBrief):  # type: ignore[no-untyped-def]
    """SQLAlchemy predicate matching campaigns belonging to a campus.

    Patterns match as WHOLE WORDS (space-bounded), not substrings — so a short
    token like 'ims' doesn't pull in 'NMIMS …' campaigns. Excludes stay broad
    (substring) so a false-match term is filtered aggressively.
    """
    name = func.lower(Campaign.name)

    def _word(p: str):  # type: ignore[no-untyped-def]
        pl = (p or "").lower().replace("%", "").replace("_", "").strip()
        if not pl:
            return None
        return or_(
            name == pl,
            name.like(f"{pl} %"),
            name.like(f"% {pl}"),
            name.like(f"% {pl} %"),
        )

    includes = [c for c in (_word(p) for p in brief.patterns()) if c is not None]
    pred = or_(*includes) if includes else false()
    if brief.exclude_terms:
        excludes = [not_(Campaign.name.ilike(f"%{x}%")) for x in brief.exclude_terms]
        pred = and_(pred, *excludes)
    return pred


class CampusService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Step 1 — campus search / autocomplete
    # ------------------------------------------------------------------ #
    def search(self, q: str | None, *, limit: int = 10) -> list[dict[str, Any]]:
        ql = (q or "").strip().lower()
        briefs = [
            b
            for b in CAMPUS_BRIEFS
            if not ql or ql in b.short.lower() or ql in b.brand.lower()
            or any(ql in a.lower() for a in b.aliases)
        ]
        # If the user typed something we don't have curated, still offer it.
        if ql and not briefs and find_brief(ql) is None:
            briefs = [generic_brief(ql)]

        out: list[dict[str, Any]] = []
        for b in briefs[:limit]:
            stats = self._campus_stats(b)
            out.append(
                {
                    "campus": b.brand,
                    "aliases": b.aliases,
                    "account_id": stats["account_id"],
                    "account_name": stats["account_name"],
                    "campaign_count": stats["campaign_count"],
                    "total_spend": stats["total_spend"],
                    "has_history": stats["campaign_count"] > 0,
                }
            )
        # Rank campuses with more history first.
        out.sort(key=lambda r: (r["has_history"], r["total_spend"]), reverse=True)
        return out

    def _campus_stats(self, brief: CampusBrief) -> dict[str, Any]:
        pred = campus_campaign_filter(brief)
        row = self.db.execute(
            select(
                func.count(func.distinct(Campaign.id)),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
                func.min(Account.id),
                func.min(Account.descriptive_name),
            )
            .select_from(Campaign)
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
            .join(Account, Campaign.account_id == Account.id)
            .where(pred)
        ).one()
        return {
            "campaign_count": int(row[0] or 0),
            "total_spend": round(float(row[1] or 0) / _MICROS, 2),
            "account_id": row[2],
            "account_name": row[3],
        }

    # ------------------------------------------------------------------ #
    # Step 2 — Final-URL discovery
    # ------------------------------------------------------------------ #
    def discover_final_url(
        self, brief: CampusBrief, *, override: str | None = None
    ) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []

        if override:
            candidates.append(
                {
                    "url": override,
                    "source": "manual",
                    "confidence": 1.0,
                    "spend": 0.0,
                    "clicks": 0,
                    "ctr": None,
                    "reason": "Manually specified by the user (overrides discovery).",
                }
            )

        candidates.extend(self._historical_urls(brief))

        if brief.homepage:
            candidates.append(
                {
                    "url": brief.homepage,
                    "source": "homepage",
                    "confidence": 0.25,
                    "spend": 0.0,
                    "clicks": 0,
                    "ctr": None,
                    "reason": (
                        "Official homepage — fallback when no historical landing page exists."
                    ),
                }
            )

        # De-dupe by URL keeping the highest-confidence entry.
        seen: dict[str, dict[str, Any]] = {}
        for c in candidates:
            u = c["url"].rstrip("/")
            if u not in seen or c["confidence"] > seen[u]["confidence"]:
                seen[u] = c
        ranked = sorted(seen.values(), key=lambda c: c["confidence"], reverse=True)
        selected = ranked[0] if ranked else None
        return {"campus": brief.brand, "selected": selected, "candidates": ranked}

    def _historical_urls(self, brief: CampusBrief) -> list[dict[str, Any]]:
        """Historical ad landing pages ranked by real performance."""
        pred = campus_campaign_filter(brief)
        cost = func.coalesce(func.sum(AdSnapshot.cost_micros), 0)
        clicks = func.coalesce(func.sum(AdSnapshot.clicks), 0)
        impr = func.coalesce(func.sum(AdSnapshot.impressions), 0)

        # Ads carry the final_urls; ad_snapshots carry per-day metrics and the
        # campaign_id we filter the campus on.
        stmt = (
            select(
                Ad.final_urls.label("final_urls"),
                cost.label("cost"),
                clicks.label("clicks"),
                impr.label("impr"),
            )
            .select_from(Ad)
            .join(AdSnapshot, AdSnapshot.ad_id == Ad.id)
            .join(Campaign, AdSnapshot.campaign_id == Campaign.id)
            .where(pred, Ad.final_urls.isnot(None), Ad.final_urls != "")
            .group_by(Ad.final_urls)
            .order_by(cost.desc())
        )
        agg: dict[str, dict[str, float]] = {}
        for r in self.db.execute(stmt).mappings():
            for url in str(r["final_urls"]).splitlines():
                url = url.strip()
                if not url:
                    continue
                a = agg.setdefault(url, {"cost": 0.0, "clicks": 0.0, "impr": 0.0})
                a["cost"] += float(r["cost"] or 0)
                a["clicks"] += float(r["clicks"] or 0)
                a["impr"] += float(r["impr"] or 0)

        total_spend = sum(a["cost"] for a in agg.values()) or 1.0
        out: list[dict[str, Any]] = []
        for url, a in agg.items():
            spend = a["cost"] / _MICROS
            ctr = (a["clicks"] / a["impr"]) if a["impr"] else None
            # Confidence: dominated by spend share, nudged by having clicks.
            share = a["cost"] / total_spend
            conf = round(min(0.98, 0.55 + 0.4 * share + (0.05 if a["clicks"] else 0)), 4)
            out.append(
                {
                    "url": url,
                    "source": "historical_ads",
                    "confidence": conf,
                    "spend": round(spend, 2),
                    "clicks": int(a["clicks"]),
                    "ctr": ctr,
                    "reason": (
                        f"Used by historical ads with ₹{spend:,.0f} spend and "
                        f"{int(a['clicks'])} clicks — highest real performance."
                    ),
                }
            )
        out.sort(key=lambda c: c["spend"], reverse=True)
        return out
