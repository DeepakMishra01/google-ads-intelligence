"""Discover the full list of colleges from real campaign names.

The warehouse has ~700 campaign names like "ABBS Bangalore || ClientLP || 2026 ||
kapp01 || ...". The college is the leading segment; the rest is channel/year/tag
noise. This groups campaigns into colleges so the whole platform can be generated
for every college, not just the 6 curated briefs.

Heuristic, not perfect — it's a starting list a human can refine.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignSnapshot

_MICROS = 1_000_000

# Channel / year / format / exam-ish tokens that are not part of a college name.
_NOISE = re.compile(
    r"\b(20\d{2}|mobile|desktop|search|display|pmax|performance ?max|lead(s)?|"
    r"client ?lp|kapp ?lp|kapplp|clientlp|our ?lp|cl|ssa|yas|kul|ca\d+|no medium|"
    r"brand|generic|exam|test|final|copy|new|old|phrase|broad|exact|max ?conv|"
    r"conversion(s)?|conv|traffic|awareness|mba|pgdm|pgp|pgpm|bba|bca|mca|"
    r"admission(s)?|apply|online|program(s|me)?|course(s)?)\b",
    re.IGNORECASE,
)
_SEPARATORS = ("||", "|", " - ", " – ", " — ")


def college_key(name: str) -> str:
    """Reduce a campaign name to its college label."""
    n = (name or "").strip()
    for sep in _SEPARATORS:
        if sep in n:
            n = n.split(sep)[0].strip()
            break
    n = _NOISE.sub(" ", n)
    n = re.sub(r"[_/]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip(" -|·.")
    return n


def discover_colleges(
    db: Session, *, min_campaigns: int = 1, min_key_len: int = 3
) -> list[dict[str, Any]]:
    """Group campaigns into colleges with campaign counts and spend."""
    rows = db.execute(
        select(
            Campaign.name,
            func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
        )
        .select_from(Campaign)
        .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id, isouter=True)
        .group_by(Campaign.id, Campaign.name)
    ).all()

    agg: dict[str, dict[str, Any]] = {}
    for name, cost in rows:
        key = college_key(name)
        if len(key) < min_key_len or key.isdigit():
            continue
        rec = agg.setdefault(key, {"college": key, "campaigns": 0, "spend": 0.0})
        rec["campaigns"] += 1
        rec["spend"] += float(cost or 0) / _MICROS

    out = [
        {"college": r["college"], "campaigns": r["campaigns"], "spend": round(r["spend"], 2)}
        for r in agg.values()
        if r["campaigns"] >= min_campaigns
    ]
    out.sort(key=lambda r: r["spend"], reverse=True)
    return out
