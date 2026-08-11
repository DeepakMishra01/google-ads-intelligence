"""Execution Audit — what we gave vs what the ad manager actually ran.

For each campaign we hold the AI plan (recommended keywords, match types, bids, ad
copy, bidding strategy). This service compares that against what is **live** in the
Google Ads account (synced ``Ad`` headlines/descriptions and ``Keyword`` text/match
type), and rolls the adherence + real performance up **per ad manager** — using only
the ad_manager assigned in the Accountability tool (never auto-derived).

Read-only over synced data; deterministic.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_group import AdGroup
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword
from app.repositories.ad_copy import AdCopyRepository
from app.services.ai.campus_config import find_brief, generic_brief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000


def _norm_kw(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\[\]"]', "", (s or "")).lower()).strip()


def _norm_copy(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).lower().strip()


def _pct(part: int, whole: int) -> int | None:
    return round(part / whole * 100) if whole else None


def _live_keywords(db: Session, brief) -> dict[str, dict[str, Any]]:
    """Normalised live keyword -> {match_type, bid} for the campus."""
    rows = db.execute(
        select(Keyword.text, Keyword.match_type, Keyword.cpc_bid_micros)
        .select_from(Keyword)
        .join(AdGroup, Keyword.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
        .where(campus_campaign_filter(brief), Keyword.text.isnot(None))
    ).all()
    out: dict[str, dict[str, Any]] = {}
    for text_, mt, bid in rows:
        out[_norm_kw(text_)] = {
            "text": text_,
            "match_type": (mt or "").upper(),
            "bid": round((bid or 0) / _MICROS, 2) if bid else None,
        }
    return out


def _live_ad_copy(db: Session, brief) -> tuple[set[str], set[str]]:
    """Sets of normalised live headlines and descriptions for the campus."""
    rows = db.execute(
        select(Ad.headlines, Ad.descriptions)
        .select_from(Ad)
        .join(AdGroup, Ad.ad_group_id == AdGroup.id)
        .join(Campaign, AdGroup.campaign_id == Campaign.id)
        .where(campus_campaign_filter(brief))
    ).all()
    heads: set[str] = set()
    descs: set[str] = set()
    for h, d in rows:
        for line in (h or "").split("\n"):
            if line.strip():
                heads.add(_norm_copy(line))
        for line in (d or "").split("\n"):
            if line.strip():
                descs.add(_norm_copy(line))
    return heads, descs


def _perf(db: Session, brief) -> dict[str, Any]:
    row = db.execute(
        select(
            func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
            func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
            func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
        )
        .select_from(Campaign)
        .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
        .where(campus_campaign_filter(brief))
    ).one()
    return {"clicks": int(row[0]), "cost": round(float(row[1]) / _MICROS, 2),
            "conversions": round(float(row[2]), 1)}


def _copy_used(rec: str, live: set[str]) -> bool:
    """Fuzzy: a recommended line counts as used if it matches, or is contained in
    (or contains) a live line — so a lightly-edited/truncated headline still counts."""
    n = _norm_copy(rec)
    if not n:
        return False
    if n in live:
        return True
    return any((n in lv or lv in n) for lv in live if len(lv) > 8)


def build_campaign_audit(db: Session, gen) -> dict[str, Any]:
    """Full given-vs-used detail for one campaign."""
    if gen is None:
        return {"available": False}
    brief = find_brief(gen.campus) or generic_brief(gen.campus)
    live_kw = _live_keywords(db, brief)
    live_h, live_d = _live_ad_copy(db, brief)

    # --- keywords ---
    rec_kw = (gen.keyword_snapshot or {}).get("keywords", [])
    used, missing = [], []
    mt_ok = 0
    for k in rec_kw:
        norm = _norm_kw(k.get("keyword"))
        if norm and norm in live_kw:
            lv = live_kw[norm]
            ok = (k.get("recommended_match_type") or "").upper() == lv["match_type"]
            mt_ok += 1 if ok else 0
            used.append({
                "keyword": k.get("keyword"),
                "recommended_match_type": k.get("recommended_match_type"),
                "live_match_type": lv["match_type"],
                "match_type_ok": ok,
            })
        else:
            missing.append(k.get("keyword"))
    rec_norms = {_norm_kw(k.get("keyword")) for k in rec_kw}
    off_plan = [
        {"text": v["text"], "match_type": v["match_type"]}
        for n, v in live_kw.items() if n not in rec_norms
    ]

    # --- ad copy ---
    assets = gen.generated_assets or {}
    rec_h = [a.get("text") for a in assets.get("headlines", []) if a.get("text")]
    rec_d = [a.get("text") for a in assets.get("descriptions", []) if a.get("text")]
    h_used = [t for t in rec_h if _copy_used(t, live_h)]
    d_used = [t for t in rec_d if _copy_used(t, live_d)]
    rec_h_norms = {_norm_copy(t) for t in rec_h}
    rec_d_norms = {_norm_copy(t) for t in rec_d}
    their_h = sorted(lv for lv in live_h if lv not in rec_h_norms)[:20]
    their_d = sorted(lv for lv in live_d if lv not in rec_d_norms)[:20]

    plan = (gen.scores or {}).get("campaign_plan") or {}
    return {
        "available": True,
        "gen_id": gen.id,
        "campus": gen.campus,
        "ad_manager": gen.ad_manager or "Unassigned",
        "keywords": {
            "recommended": len(rec_kw),
            "used": len(used),
            "adoption_pct": _pct(len(used), len(rec_kw)),
            "match_type_adherence_pct": _pct(mt_ok, len(used)),
            "used_list": used[:50],
            "missing": [m for m in missing if m][:50],
            "off_plan": off_plan[:50],
            "live_total": len(live_kw),
        },
        "ad_copy": {
            "headlines": {
                "recommended": len(rec_h), "used": len(h_used),
                "adoption_pct": _pct(len(h_used), len(rec_h)),
                "used_list": h_used, "unused_list": [t for t in rec_h if t not in h_used],
                "their_own": their_h,
            },
            "descriptions": {
                "recommended": len(rec_d), "used": len(d_used),
                "adoption_pct": _pct(len(d_used), len(rec_d)),
                "used_list": d_used, "unused_list": [t for t in rec_d if t not in d_used],
                "their_own": their_d,
            },
        },
        "strategy": {
            "recommended_bidding": (plan.get("bidding") or {}).get("recommended"),
            "budget": (plan.get("forecast") or {}).get("budget"),
        },
        "performance": _perf(db, brief),
    }


def _light_audit(db: Session, gen) -> dict[str, Any]:
    """A per-campaign summary for the manager rollup (adherence % + performance)."""
    a = build_campaign_audit(db, gen)
    if not a.get("available"):
        return a
    kw, hl, dl = a["keywords"], a["ad_copy"]["headlines"], a["ad_copy"]["descriptions"]
    copy_rec = hl["recommended"] + dl["recommended"]
    copy_used = hl["used"] + dl["used"]
    return {
        "gen_id": gen.id,
        "campus": gen.campus,
        "kw_adoption_pct": kw["adoption_pct"],
        "match_type_adherence_pct": kw["match_type_adherence_pct"],
        "copy_adoption_pct": _pct(copy_used, copy_rec),
        "clicks": a["performance"]["clicks"],
        "cost": a["performance"]["cost"],
        "conversions": a["performance"]["conversions"],
    }


def build_manager_audit(
    db: Session, *, allowed_account_ids: set[int] | None = None
) -> dict[str, Any]:
    """Adherence + performance per ad manager (assigned managers only).

    ``allowed_account_ids`` (None = admin/all) scopes to a manager's own accounts.
    """
    gens = [g for g in AdCopyRepository(db).latest_per_campus() if g.ad_manager]
    if allowed_account_ids is not None:
        gens = [g for g in gens if g.account_id in allowed_account_ids]
    by_mgr: dict[str, list[dict[str, Any]]] = {}
    for g in gens:
        by_mgr.setdefault(g.ad_manager, []).append(_light_audit(db, g))

    def _avg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(vals) / len(vals)) if vals else None

    managers = []
    for mgr, rows in sorted(by_mgr.items()):
        managers.append({
            "ad_manager": mgr,
            "campaigns": len(rows),
            "kw_adoption_pct": _avg(rows, "kw_adoption_pct"),
            "copy_adoption_pct": _avg(rows, "copy_adoption_pct"),
            "match_type_adherence_pct": _avg(rows, "match_type_adherence_pct"),
            "clicks": sum(r["clicks"] for r in rows),
            "cost": round(sum(r["cost"] for r in rows), 2),
            "conversions": round(sum(r["conversions"] for r in rows), 1),
            "campaign_rows": rows,
        })
    return {"managers": managers, "assigned_campaigns": len(gens)}
