"""AI Ad Copy orchestrator (Steps 1-11).

Composes campus discovery, landing-page analysis, historical intelligence,
keyword research/scoring, generation (hybrid LLM or deterministic), validation,
and persistence into one explainable result. Every asset carries a data-derived
reason; the LLM (when configured) only rephrases within the data it is given.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai_clients.llm_client import get_llm_client
from app.config.logging import get_logger
from app.repositories.ad_copy import AdCopyRepository, ScorecardSnapshotRepository
from app.services.ai import intent_classifier
from app.services.ai.bid_auction_service import build_bid_audit
from app.services.ai.budget_planner import build_plan
from app.services.ai.campaign_scorecard import build_scorecard
from app.services.ai.campus_config import _is_online, find_brief, generic_brief
from app.services.ai.campus_service import CampusService, campus_campaign_filter
from app.services.ai.cpl_optimizer import build_cpl_plan
from app.services.ai.historical_intelligence_service import HistoricalIntelligenceService
from app.services.ai.keyword_history_service import build_keyword_history
from app.services.ai.keyword_research_service import KeywordResearchService
from app.services.ai.keyword_scorer import recommend_bid, recommend_match_type, score_keyword
from app.services.ai.landing_auditor import build_landing_audit
from app.services.ai.landing_page_service import LandingPageService
from app.services.ai.landing_quality import score_landing_page
from app.services.ai.last_year_summary import build_last_year_summary
from app.services.ai.negative_keywords_service import build_negative_keywords
from app.services.ai.reverse_planner import build_reverse_plan
from app.services.ai.rsa_validator import D_MAX, H_MAX, validate_assets
from app.services.ai.scorecard_alerts import build_week_alerts
from app.services.ai.search_terms_service import build_top_search_terms
from app.services.ai.seasonality_service import build_seasonality
from app.services.ai.setup_guide import build_setup_guide

log = get_logger(__name__)

def _fit(text: str, limit: int) -> str | None:
    t = re.sub(r"\s+", " ", (text or "")).strip(" -|")
    return t if 1 <= len(t) <= limit else None


# Programme/degree acronyms that must stay upper-cased in headlines.
_ACRONYMS = {
    "mba", "pgdm", "pgpm", "bba", "bca", "mca", "mbbs", "bds", "llb", "llm", "phd",
    "bpt", "bams", "bhms", "msc", "bsc", "mcom", "bcom", "ba", "ma", "cuet", "cat",
    "nmat", "micat", "clat", "gate", "iit", "nit", "iim", "ug", "pg",
}


def _titlecase(s: str) -> str:
    out: list[str] = []
    for w in s.split():
        wl = w.lower().strip(".")
        if wl in _ACRONYMS:
            out.append(wl.upper())
        elif wl in ("btech", "b.tech"):
            out.append("B.Tech")
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _match_format(keyword: str, match_type: str) -> str:
    """Google Ads match-type syntax: [exact], "phrase", broad."""
    kw = keyword.strip()
    if match_type == "EXACT":
        return f"[{kw}]"
    if match_type == "PHRASE":
        return f'"{kw}"'
    return kw  # BROAD


def _match_formats(keyword: str, match_type: str) -> list[str]:
    """Paste-ready forms for a keyword. 'BOTH' → phrase AND exact (two entries)."""
    if (match_type or "").upper() == "BOTH":
        return [_match_format(keyword, "PHRASE"), _match_format(keyword, "EXACT")]
    return [_match_format(keyword, match_type)]


# Funnel tiers for ad-copy prioritisation. BOF (bottom-of-funnel) = ready-to-act
# intents that convert best — they lead the headlines and get pinned. MOF
# (mid-of-funnel) = consideration intents (fees / courses / eligibility / placement)
# — surfaced only when they genuinely rank among the campus's top keywords, never
# as generic filler. Everything else (location / generic / research) is TOF.
_BOF_INTENTS = {"brand", "admission", "application", "registration", "deadline"}
_MOF_INTENTS = {"fees", "course", "courses", "eligibility", "placement"}


def _intent_tier(intent: str | None) -> int:
    i = (intent or "").lower()
    if i in _BOF_INTENTS:
        return 0
    if i in _MOF_INTENTS:
        return 1
    return 2  # top-of-funnel: location / generic / research


# Programme acronyms we can reliably read off a landing page (word-boundary), to
# seed keywords + copy with the courses the college actually offers.
_LANDING_PROGRAMS = [
    ("MBA", r"\bmba\b"), ("PGDM", r"\bpgdm\b"), ("PGPM", r"\bpgpm\b"),
    ("BBA", r"\bbba\b"), ("BCA", r"\bbca\b"), ("MCA", r"\bmca\b"),
    ("B.Tech", r"\bb\.?tech\b"), ("M.Tech", r"\bm\.?tech\b"),
    ("B.Com", r"\bb\.?com\b"), ("M.Com", r"\bm\.?com\b"),
    ("BSc", r"\bb\.?sc\b"), ("MSc", r"\bm\.?sc\b"),
    ("BA", r"\bb\.?a\b"), ("MA", r"\bm\.?a\b"),
    ("LLB", r"\bllb\b"), ("LLM", r"\bllm\b"), ("PhD", r"\bph\.?d\b"),
    ("Diploma", r"\bdiploma\b"),
]


def _programs_from_landing(landing: dict[str, Any], online: bool) -> list[str]:
    """Programme names actually present on the landing page (drives relevance)."""
    blob = " ".join(landing.get("courses", []) or []).lower()
    if not blob:
        return []
    found = [label for label, rx in _LANDING_PROGRAMS if re.search(rx, blob)]
    return [f"Online {p}" for p in found] if online else found


class AdCopyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.campus = CampusService(db)
        self.landing = LandingPageService(db)
        self.history = HistoricalIntelligenceService(db)
        self.keywords = KeywordResearchService(db)
        self.repo = AdCopyRepository(db)
        self.scorecards = ScorecardSnapshotRepository(db)
        self.llm = get_llm_client()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def search_campus(self, q: str | None, *, limit: int = 10) -> dict[str, Any]:
        return {"items": self.campus.search(q, limit=limit)}

    def discover_url(self, campus: str, *, override: str | None = None) -> dict[str, Any]:
        brief = find_brief(campus) or generic_brief(campus)
        return self.campus.discover_final_url(brief, override=override)

    def _device_stats(self, brief) -> dict[str, Any] | None:
        """Mobile share + raw click counts for the campus (real device data).

        Returns the grounding for the 88%-mobile claim: the actual mobile and
        total click counts it's computed from.
        """
        from sqlalchemy import func, select

        from app.models.campaign import Campaign, CampaignDeviceSnapshot

        rows = self.db.execute(
            select(
                CampaignDeviceSnapshot.device,
                func.coalesce(func.sum(CampaignDeviceSnapshot.clicks), 0),
            )
            .select_from(Campaign)
            .join(CampaignDeviceSnapshot, CampaignDeviceSnapshot.campaign_id == Campaign.id)
            .where(campus_campaign_filter(brief))
            .group_by(CampaignDeviceSnapshot.device)
        ).all()
        by_dev = {(d or "").upper(): int(c) for d, c in rows}
        total = sum(by_dev.values())
        if total <= 0:
            return None
        mobile = by_dev.get("MOBILE", 0)
        return {"share": round(mobile / total, 4), "mobile": mobile, "total": total}

    def _mobile_share(self, brief) -> float | None:
        stats = self._device_stats(brief)
        return stats["share"] if stats else None

    def _history_stats(self, brief) -> dict[str, Any] | None:
        """Real annualised clicks/spend/CPC/CTR for the campus (deduped snapshots).

        The anchor for the forecast reality-check: what the account actually
        achieves, so we don't extrapolate 10× budget at a flat brand CPC.
        """
        from sqlalchemy import func, select

        from app.models.campaign import Campaign, CampaignSnapshot

        row = self.db.execute(
            select(
                func.min(CampaignSnapshot.snapshot_date),
                func.max(CampaignSnapshot.snapshot_date),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
            )
            .select_from(Campaign)
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
            .where(campus_campaign_filter(brief))
        ).one()
        mn, mx, clk, impr, cost = row
        clk, impr, cost = int(clk or 0), int(impr or 0), float(cost or 0) / 1_000_000
        if not (mn and mx and clk > 0):
            return None
        days = max(1, (mx - mn).days + 1)
        return {
            "clicks_per_year": clk * 365 / days,
            "spend_per_year": cost * 365 / days,
            "cpc": (cost / clk) if clk else None,
            "ctr": (clk / impr) if impr else None,
        }

    @staticmethod
    def _annual_demand(campus_kw: list[dict[str, Any]]) -> int | None:
        """Total yearly search demand across the campus's own keywords."""
        total = 0
        for k in campus_kw:
            mv = k.get("monthly_search_volumes") or []
            total += (
                sum(v.get("searches", 0) for v in mv)
                if mv
                else (k.get("search_volume") or 0) * 12
            )
        return int(total) or None

    def generate(
        self,
        *,
        campus: str,
        account_id: int | None = None,
        final_url: str | None = None,
        tone: str | None = None,
        persist: bool = True,
        actor: str | None = None,
        budget: float | None = None,
        goal: str = "traffic",
        timeframe_months: int = 12,
        assumed_cvr: float = 0.15,  # TARGET click→lead conversion for planning (15% benchmark)
        target_cpl_low: float = 750.0,
        target_cpl_high: float = 850.0,
        target_leads: int = 2000,  # goal for the reverse planner
        conversion_tracking: str = "auto",  # auto | yes | no — this year's tracking status
        lp_type: str = "auto",  # auto | kapp | client — landing-page ownership
        manual_cpc: float | None = None,  # cold-start CPC override (else peer benchmark)
    ) -> dict[str, Any]:
        brief = find_brief(campus) or generic_brief(campus)

        # Step 2: Final URL.
        url_result = self.campus.discover_final_url(brief, override=final_url)
        selected = url_result["selected"]

        # Step 3: landing page.
        landing = self.landing.analyze(selected["url"] if selected else None)

        # Enrich the brief's programmes with what the landing page ACTUALLY offers,
        # so keywords AND ad copy reflect the real courses (especially for online /
        # uncurated colleges) instead of a generic "Admissions" seed.
        lp_programs = _programs_from_landing(landing, _is_online(campus))
        if lp_programs:
            from dataclasses import replace

            base_progs = [p for p in brief.programs
                          if p.lower() not in ("admissions", "admission")]
            merged = list(dict.fromkeys([*lp_programs, *base_progs])) or brief.programs
            brief = replace(brief, programs=merged[:8])

        # Step 4: historical intelligence.
        historical = self.history.analyze(brief)

        # Steps 5-7: keyword research → intent → scoring.
        raw_kw, providers_used = self.keywords.collect(brief)
        # This year's conversion-tracking status drives the strategy. The account
        # manager can override the historical auto-detection (tracking is being set
        # up this year via the Google landing page).
        detected_conv = (historical.get("total_conversions") or 0) > 0
        has_conversions = (
            True if conversion_tracking == "yes"
            else False if conversion_tracking == "no"
            else detected_conv
        )
        keyword_insights = self._score_keywords(brief, raw_kw, has_conversions=has_conversions)
        keyword_groups = self._group_keywords(keyword_insights)

        # Step 9: generation (hybrid LLM → deterministic fallback).
        context = self._build_context(brief, landing, historical, keyword_insights, tone)
        assets, backend = self._generate_assets(context)

        # Structural assets are data-derived (grounded, not invented).
        assets["display_paths"] = self._paths(brief, keyword_insights)
        assets["callouts"] = assets.get("callouts") or self._callouts(brief, landing)
        assets["structured_snippets"] = self._snippets(brief, landing)
        assets["sitelinks"] = self._sitelinks(brief, selected)
        negatives = build_negative_keywords(self.db, brief)
        assets["negative_keywords"] = negatives["keywords"]

        # Step 10: validation + quality prediction.
        quality = validate_assets(
            headlines=[a["text"] for a in assets["headlines"]],
            descriptions=[a["text"] for a in assets["descriptions"]],
            display_paths=assets["display_paths"],
            callouts=assets["callouts"],
            keyword_themes=historical["best_keyword_themes"] or brief.programs,
        )

        recommendation = self._campaign_recommendation(brief, keyword_groups)
        dstats = self._device_stats(brief)

        # Keyword performance history — "keep or drop last time's keywords?"
        # (campus-scoped real month-on-month + keep/review/drop verdicts).
        keyword_history = build_keyword_history(
            self.db, brief, [k["keyword"] for k in keyword_insights]
        )

        # Top real search terms for this college (actual queries + metrics).
        top_search_terms = build_top_search_terms(self.db, brief, limit=25)

        # Seasonality (Keyword Planner month-on-month) + budget plan (when a budget is given).
        # IMPORTANT: only aggregate THIS campus's own demand. Two traps:
        #  1) Keyword Planner returns broad "related ideas" (e.g. "ignou admission",
        #     "b tech", "iti admission") with huge national volumes — summing those
        #     inflates the curve ~20×.
        #  2) A bare brand token can be ambiguous ("indus" also = IndusInd Bank / Indus
        #     Valley). So we require the full brand phrase (short form for long names,
        #     e.g. "gibs"; full name otherwise, e.g. "indus university").
        base = (brief.short if len(brief.brand.split()) >= 3 else brief.brand).lower()
        campus_kw = [k for k in raw_kw if base in k["keyword"].lower()]
        seasonality = build_seasonality(campus_kw, has_exam=bool(brief.exam))
        # Cold-start: when this campus has no CPC history of its own, anchor the plan
        # to the median across your existing colleges instead of a flat constant.
        hist_stats = self._history_stats(brief)
        peer = None
        if not (hist_stats and hist_stats.get("cpc")):
            from app.services.ai.peer_benchmarks import peer_benchmarks

            peer = peer_benchmarks(self.db)

        campaign_plan = None
        if budget and budget > 0:
            campaign_plan = build_plan(
                budget=float(budget),
                timeframe_months=timeframe_months,
                goal=goal,
                assumed_cvr=assumed_cvr,
                keyword_groups=keyword_groups,
                keyword_insights=keyword_insights,
                seasonality=seasonality,
                mobile_share=(dstats or {}).get("share"),
                mobile_clicks=(dstats or {}).get("mobile"),
                total_device_clicks=(dstats or {}).get("total"),
                has_conversions=has_conversions,
                hist_stats=hist_stats,
                annual_search_demand=self._annual_demand(campus_kw),
                benchmark_cpc=(peer or {}).get("cpc"),
                manual_cpc=manual_cpc,
            )
            # CPL target optimizer — required conversion rate + gap + playbook.
            if campaign_plan and campaign_plan.get("available"):
                alloc = campaign_plan.get("allocation", [])
                p1 = [r for r in alloc if r.get("phase") == 1 and r.get("avg_cpc")]
                tot_b = sum(r["budget"] for r in p1) or 1
                opt_cpc = (
                    sum(r["avg_cpc"] * r["budget"] for r in p1) / tot_b if p1 else None
                )
                blended = (campaign_plan.get("forecast") or {}).get("blended_cpc") or opt_cpc
                campaign_plan["cpl_plan"] = build_cpl_plan(
                    budget=float(budget),
                    blended_cpc=blended,
                    optimized_cpc=opt_cpc,
                    target_cpl_low=target_cpl_low,
                    target_cpl_high=target_cpl_high,
                )
                # Reverse planner: start from the GOAL, compute required inputs.
                campaign_plan["reverse_plan"] = build_reverse_plan(
                    target_leads=target_leads or 2000,
                    target_cpl=(target_cpl_low + target_cpl_high) / 2,
                    cpc=blended,
                    cvr_pct=(assumed_cvr or 0.15) * 100,
                    annual_search_demand=self._annual_demand(campus_kw),
                )

        # Bid / auction accountability — real CPC vs Google's top-of-page range.
        bid_audit = build_bid_audit(keyword_insights)

        # Landing-page quality score + specific fixes (biggest CVR lever).
        landing_quality = score_landing_page(
            landing, mobile_heavy=((dstats or {}).get("share") or 0) >= 0.6
        )
        # Landing-page auditor: tracking placement + reuse/rebuild verdict (Kapp LPs).
        landing_audit = build_landing_audit(
            landing, landing_quality, lp_type=lp_type, brand=brief.brand
        )

        # Last-year learning summary — evidence-backed "what to fix and why".
        last_year = build_last_year_summary(
            keyword_history=keyword_history,
            negatives=negatives,
            landing_quality=landing_quality,
            has_conversions=has_conversions,
        )

        # Campaign setup guide — a from-scratch checklist for a Google Ads newcomer.
        setup_guide = build_setup_guide(
            campaign_name=recommendation.get("campaign_name", brief.brand),
            plan=campaign_plan,
            keyword_groups=keyword_groups,
            negatives=assets.get("negative_keywords", []),
            geo=brief.location,
            has_conversions=has_conversions,
            total_keywords=len(keyword_insights),
        )

        result: dict[str, Any] = {
            "campus": brief.brand,
            "backend": backend,
            "final_url": selected,
            "landing_page": landing,
            "historical": historical,
            "keywords": keyword_insights,
            "keyword_groups": keyword_groups,
            "campaign_recommendation": recommendation,
            "assets": assets,
            "quality": quality,
            "seasonality": seasonality,
            "campaign_plan": campaign_plan,
            "keyword_history": keyword_history,
            "bid_audit": bid_audit,
            "top_search_terms": top_search_terms,
            "setup_guide": setup_guide,
            "negative_keywords_detail": negatives,
            "landing_quality": landing_quality,
            "landing_audit": landing_audit,
            "last_year_summary": last_year,
            "generated_at": datetime.now(UTC),
            "providers_used": providers_used,
        }

        gen_id = None
        if persist:
            gen_id = self._persist(brief, account_id, actor, selected, backend, historical,
                                   keyword_insights, assets, quality, result)
        result["id"] = gen_id
        return result

    def scorecard(
        self, *, campus: str, account_id: int | None = None, target_leads: int = 2000
    ) -> dict[str, Any]:
        """Objective vs expected vs achieved for a campus's saved plan(s)."""
        brief = find_brief(campus) or generic_brief(campus)
        gens = self.repo.recent(campus=campus, limit=5)
        gen = gens[0] if gens else None
        prev_gen = gens[1] if len(gens) > 1 else None
        return build_scorecard(
            self.db, brief, gen=gen, prev_gen=prev_gen, target_leads=target_leads
        )

    def save_scorecard(
        self, *, campus: str, account_id: int | None = None, target_leads: int = 2000
    ) -> dict[str, Any]:
        """Compute the current scorecard and persist it as a weekly snapshot."""
        sc = self.scorecard(campus=campus, account_id=account_id, target_leads=target_leads)
        if not sc.get("available"):
            return {"saved": False, "reason": sc.get("reason")}
        gens = self.repo.recent(campus=campus, limit=1)
        ac = sc.get("achieved") or {}
        ex = sc.get("expected") or {}
        impl = sc.get("implementation") or {}
        row = self.scorecards.save(
            {
                "campus": sc.get("campus", campus),
                "account_id": account_id,
                "generation_id": gens[0].id if gens else None,
                "achieved_leads": ac.get("leads"),
                "achieved_cost": ac.get("cost"),
                "achieved_clicks": ac.get("clicks"),
                "implementation_pct": impl.get("score_pct") if impl.get("available") else None,
                "expected_leads": ex.get("leads"),
                "target_leads": target_leads,
                "payload": sc,
            }
        )
        self.db.commit()
        return {"saved": True, "id": row.id}

    def scorecard_history(self, *, campus: str, limit: int = 12) -> dict[str, Any]:
        def _f(v: Any) -> float | None:
            return float(v) if v is not None else None

        rows = self.scorecards.history(campus=campus, limit=limit)
        items = [
            {
                "id": r.id,
                "date": r.created_at.date().isoformat() if r.created_at else None,
                "achieved_leads": _f(r.achieved_leads),
                "achieved_cost": _f(r.achieved_cost),
                "achieved_clicks": r.achieved_clicks,
                "implementation_pct": r.implementation_pct,
                "expected_leads": _f(r.expected_leads),
                "target_leads": r.target_leads,
            }
            for r in rows
        ]
        return {"items": items, "week_alerts": build_week_alerts(items)}

    def history_rows(self, *, campus: str | None = None, limit: int = 50) -> dict[str, Any]:
        rows = self.repo.recent(campus=campus, limit=limit)
        return {
            "items": [
                {
                    "id": r.id,
                    "campus": r.campus,
                    "final_url": r.final_url,
                    "backend": r.backend,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
        }

    def get_generation(self, gen_id: int):  # type: ignore[no-untyped-def]
        return self.repo.get(gen_id)

    def get_plan(self, gen_id: int) -> dict[str, Any] | None:
        """Re-open a saved generation's full result payload (for the UI).

        Returns the exact ``generate()`` result stored at generation time, so a
        plan survives navigation/reload. Returns None for a missing plan or an old
        generation created before result payloads were saved.
        """
        gen = self.repo.get(gen_id)
        if gen is None or not gen.result_payload:
            return None
        payload = dict(gen.result_payload)
        payload["id"] = gen.id  # the payload was stored before the id was assigned
        # Restore the ad manager's saved edits so the editors re-open with them.
        payload["keyword_edits"] = gen.keyword_edits
        payload["asset_edits"] = gen.asset_edits
        return payload

    # ------------------------------------------------------------------ #
    # User keyword edits (add / remove / overwrite)
    # ------------------------------------------------------------------ #
    def lookup_keywords(self, keywords: list[str]) -> list[dict[str, Any]]:
        """Keyword Planner metrics for exact user-typed keywords."""
        from app.services.ai.keyword_research_service import KeywordResearchService

        return KeywordResearchService(self.db).lookup_metrics(keywords)

    def save_keyword_edits(
        self, gen_id: int, *, added: list[dict[str, Any]], removed: list[str],
        overrides: dict[str, dict[str, Any]] | None = None, actor: str | None,
    ) -> dict[str, Any]:
        """Persist the user's keyword edits on a generation.

        Editing the plan resets approval to draft (it must be re-approved), and the
        change is logged so the review email can show what was added/removed.
        """
        from app.services.ai.approval_service import ApprovalService

        gen = self.repo.get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}

        brief = find_brief(gen.campus) or generic_brief(gen.campus)
        # Classify each user-added keyword through the SAME pipeline as the system
        # ones (intent + match type + bid) so it folds into the right ad group.
        norm_added = self._classify_added(brief, added or [])
        removed_norm = sorted({(r or "").strip() for r in (removed or []) if (r or "").strip()})
        removed_lc = {r.lower() for r in removed_norm}

        # Recompute the effective ad-group structure: system suggestions (minus the
        # removed) + the classified user-added keywords, re-grouped by intent.
        system = [
            k for k in (gen.keyword_snapshot or {}).get("keywords", [])
            if (k.get("keyword") or "").lower() not in removed_lc
        ]
        effective = system + norm_added
        # Apply the user's per-keyword intent/match overrides BEFORE grouping so the
        # keyword lands in the ad group the user chose, and mark what they changed.
        ov = {(k or "").strip().lower(): v for k, v in (overrides or {}).items()}
        clean_overrides: dict[str, dict[str, Any]] = {}
        for kw in effective:
            o = ov.get((kw.get("keyword") or "").lower())
            if not o:
                continue
            entry: dict[str, Any] = {}
            if o.get("intent"):
                kw["intent"] = str(o["intent"]).lower()
                entry["intent"] = kw["intent"]
            if o.get("match_type"):
                kw["recommended_match_type"] = str(o["match_type"]).upper()
                entry["match_type"] = kw["recommended_match_type"]
            if entry:
                clean_overrides[kw["keyword"]] = entry

        self._fill_bid_gaps(effective)
        groups = self._group_keywords(effective)

        gen.keyword_edits = {"added": norm_added, "removed": removed_norm,
                             "overrides": clean_overrides, "groups": groups}
        # Refresh the ad copy so it reflects the edited keywords — UNLESS the ad
        # manager has manually edited the copy (their copy then stands; the
        # "Regenerate ad copy" button overrides that on demand).
        regenerated = False
        if not gen.asset_edits:
            try:
                self._regenerate_copy(gen, brief=brief)
                regenerated = True
            except Exception as exc:  # noqa: BLE001
                log.info("adcopy.regen_on_edit_failed", error=str(exc))
        # A changed plan can't keep a stale approval.
        if gen.approval_status in ("submitted", "approved", "rejected", "changes_requested"):
            gen.approval_status = "draft"
        self.db.flush()
        ApprovalService(self.db).events.add_event(
            gen_id, "keywords_edited", actor,
            f"+{len(norm_added)} added, -{len(removed_norm)} removed, "
            f"{len(clean_overrides)} edited"
            + (" · ad copy refreshed" if regenerated else ""),
        )
        self.db.commit()
        return {"ok": True, "gen_id": gen_id, "added": len(norm_added),
                "removed": len(removed_norm), "edited": len(clean_overrides),
                "keyword_groups": groups, "copy_regenerated": regenerated}

    def save_asset_edits(
        self, gen_id: int, *,
        headlines: list[str] | None = None,
        descriptions: list[str] | None = None,
        callouts: list[str] | None = None,
        actor: str | None,
    ) -> dict[str, Any]:
        """Persist the ad manager's edits to the generated ad copy.

        Each provided list is the FULL desired set for that asset kind (edited +
        added lines). Editing resets approval to draft (it must be re-approved), and
        the change is logged so the review email can flag copy the ad manager
        edited/added. Entries over the Google Ads character limit are rejected.
        """
        from app.services.ai.approval_service import ApprovalService, effective_assets

        gen = self.repo.get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}

        limits = {"headlines": H_MAX, "descriptions": D_MAX, "callouts": 25}
        incoming = {"headlines": headlines, "descriptions": descriptions,
                    "callouts": callouts}
        edits = dict(gen.asset_edits or {})
        invalid: list[dict[str, Any]] = []
        for kind, items in incoming.items():
            if items is None:  # not touched this save
                continue
            cleaned: list[str] = []
            seen: set[str] = set()
            for raw in items:
                t = re.sub(r"\s+", " ", (raw or "")).strip()
                if not t or t.lower() in seen:
                    continue
                if len(t) > limits[kind]:
                    invalid.append({"kind": kind, "text": t, "length": len(t),
                                    "limit": limits[kind]})
                    continue
                seen.add(t.lower())
                cleaned.append(t)
            edits[kind] = cleaned
        if invalid:
            return {"ok": False,
                    "reason": "Some lines exceed the Google Ads character limit.",
                    "invalid": invalid}

        edits["by"] = actor
        edits["at"] = datetime.now(UTC).isoformat()
        gen.asset_edits = edits
        if gen.approval_status in ("submitted", "approved", "rejected", "changes_requested"):
            gen.approval_status = "draft"
        self.db.flush()
        ea = effective_assets(gen)
        ApprovalService(self.db).events.add_event(
            gen_id, "adcopy_edited", actor,
            f"{ea['edited_count']} line(s) edited/added by ad manager",
        )
        self.db.commit()
        return {"ok": True, "gen_id": gen_id, "edited_count": ea["edited_count"],
                "assets": {k: ea[k] for k in ("headlines", "descriptions", "callouts")}}

    def _regenerate_copy(self, gen, *, brief=None) -> str:  # type: ignore[no-untyped-def]
        """Regenerate headlines/descriptions/callouts from the plan's CURRENT keywords.

        Rebuilds the generation context from the stored landing/historical data plus
        the effective (edited) keyword set, so the ad copy reflects the keywords.
        Only the copy is refreshed; structural assets (paths / sitelinks / snippets /
        negatives) are kept. Returns the backend used ("llm" | "template").
        """
        from app.services.ai.approval_service import effective_keywords

        brief = brief or find_brief(gen.campus) or generic_brief(gen.campus)
        active, _removed = effective_keywords(gen)
        active = sorted(active, key=lambda k: k.get("score") or 0, reverse=True)
        payload = gen.result_payload or {}
        landing = payload.get("landing_page") or {}
        hist = gen.historical_features_used or {}
        historical = {
            "top_headlines": hist.get("top_headlines", []) or [],
            "top_descriptions": [],
            "best_keyword_themes": hist.get("keyword_themes", []) or [],
        }
        context = self._build_context(brief, landing, historical, active, None)
        assets, backend = self._generate_assets(context)
        merged = dict(gen.generated_assets or {})
        merged["headlines"] = assets["headlines"]
        merged["descriptions"] = assets["descriptions"]
        if assets.get("callouts"):
            merged["callouts"] = assets["callouts"]
        gen.generated_assets = merged
        if gen.result_payload:
            rp = dict(gen.result_payload)
            rp["assets"] = merged
            gen.result_payload = rp
        return backend

    def regenerate_copy(self, gen_id: int, *, actor: str | None) -> dict[str, Any]:
        """Explicitly rebuild the ad copy from the current keywords (button action).

        Discards any manual copy edits (the ad manager asked for fresh copy) and
        resets approval to draft.
        """
        from app.services.ai.approval_service import ApprovalService

        gen = self.repo.get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        gen.asset_edits = None  # explicit regenerate → discard manual copy edits
        if gen.result_payload:
            rp = dict(gen.result_payload)
            rp["asset_edits"] = None
            gen.result_payload = rp
        try:
            backend = self._regenerate_copy(gen)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return {"ok": False, "reason": f"could not regenerate: {exc}"}
        if gen.approval_status in ("submitted", "approved", "rejected", "changes_requested"):
            gen.approval_status = "draft"
        self.db.flush()
        ApprovalService(self.db).events.add_event(
            gen_id, "adcopy_regenerated", actor, "from current keywords"
        )
        self.db.commit()
        return {"ok": True, "backend": backend,
                "assets": {k: gen.generated_assets.get(k)
                           for k in ("headlines", "descriptions", "callouts")}}

    def _classify_added(self, brief, added: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Turn user-added keyword dicts into full scored insights (intent/match/bid)."""
        brand_terms = brief.patterns()
        brand_set = self._brand_keywords(brief)
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for a in added:
            text = (a.get("keyword") or "").strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            cls = intent_classifier.classify(text, brand_terms=brand_terms)
            base = {
                "keyword": text, "source": "user_added",
                "search_volume": a.get("search_volume"), "competition": a.get("competition"),
                "historical_clicks": None, "historical_ctr": None,
                "historical_cpc": a.get("historical_cpc"),
                "top_of_page_bid_low": a.get("top_of_page_bid_low"),
                "top_of_page_bid_high": a.get("top_of_page_bid_high"),
                "quality_score": None,
                "commercial_intent": cls["commercial_intent"],
                "intent_confidence": cls["confidence"],
            }
            sc = score_keyword(base)
            is_brand = text.lower() in brand_set
            intent = "brand" if is_brand else cls["intent"]
            score = max(sc["score"], 80.0 if is_brand else 55.0)
            out.append({
                **base,
                "intent": intent,
                "score": round(score, 1),
                "reason": f"Added by user. {cls['reason']}",
                **recommend_bid(base),
                **recommend_match_type(
                    {"intent": intent, "historical_clicks": None, "historical_ctr": None},
                    has_conversions=False,
                ),
            })
        return out

    # ------------------------------------------------------------------ #
    # keyword scoring + grouping
    # ------------------------------------------------------------------ #
    def _brand_keywords(self, brief) -> set[str]:
        """Pure brand terms — the college name, abbreviation, aliases, +location."""
        base = brief.brand.lower()
        short = brief.short.lower()
        terms = {base, short, *[a.lower() for a in brief.aliases]}
        # Add a "... college" variant only when the name has no institution word.
        inst = ("university", "institute", "school", "college", "academy")
        if not any(w in base for w in inst):
            terms.add(f"{base} college")
        if not any(w in short for w in inst):
            terms.add(f"{short} college")
        if brief.exam:
            terms.add(brief.exam.lower())
        if brief.location:
            loc = brief.location.lower()
            terms.add(f"{base} {loc}")
            terms.add(f"{short} {loc}")
        return {t.strip() for t in terms if t.strip()}

    def _keyword_plan(self, brief) -> list[dict[str, Any]]:
        """Generate a clean brand + intent keyword plan (the strategist baseline).

        Mirrors how these accounts actually bid — the brand paired with admission
        intents — so the campaign gets relevant keywords even when historical data
        is thin or polluted with broad-match spillover.
        """
        # For long names (GIBS Business School, Goa Institute of Management) people
        # search the short form (gibs, gim); for 1-2 word brands use the full name.
        base = (brief.short if len(brief.brand.split()) >= 3 else brief.brand).lower()
        empty = {"source": "suggested", "search_volume": None, "competition": None,
                 "historical_clicks": None, "historical_ctr": None,
                 "historical_cpc": None, "quality_score": None}
        terms = [
            base,
            f"{base} admission", f"{base} admissions 2026", f"{base} apply online",
            f"{base} application form", f"{base} admission form", f"{base} fees",
            f"{base} fee structure", f"{base} courses", f"{base} eligibility",
            f"{base} placements", f"{base} last date to apply",
        ]
        for p in brief.programs:
            pl = p.lower()
            if pl in ("admissions", "admission"):
                continue
            terms += [f"{base} {pl}", f"{base} {pl} admission", f"{base} {pl} fees"]
        if brief.location:
            terms.append(f"{base} {brief.location.lower()} admission")
        if brief.exam:
            ex = brief.exam.lower()
            terms += [f"{ex} registration", f"{ex} 2026", f"register for {ex}",
                      f"{ex} application form", f"{ex} last date"]
        return [{"keyword": t, **empty} for t in dict.fromkeys(terms)]

    def _score_keywords(
        self, brief, raw_kw: list[dict[str, Any]], *, has_conversions: bool = False
    ) -> list[dict[str, Any]]:
        patterns = brief.patterns()

        def is_relevant(kw: str) -> bool:
            return any(p in kw.lower() for p in patterns)

        # Drop broad-match spillover: keep only keywords that mention this campus.
        historical = [kw for kw in raw_kw if is_relevant(kw["keyword"])]
        brand_set = self._brand_keywords(brief)
        # Merge the generated brand plan + pure brand keywords (dedupe by text).
        seen = {kw["keyword"].lower() for kw in historical}
        empty = {"source": "suggested", "search_volume": None, "competition": None,
                 "historical_clicks": None, "historical_ctr": None,
                 "historical_cpc": None, "quality_score": None}
        extras = [{"keyword": b, **empty} for b in sorted(brand_set)]
        extras += self._keyword_plan(brief)
        candidates = historical + [e for e in extras if e["keyword"].lower() not in seen]

        brand_terms = brief.patterns()
        insights: list[dict[str, Any]] = []
        for kw in candidates:
            cls = intent_classifier.classify(kw["keyword"], brand_terms=brand_terms)
            merged = {**kw, "commercial_intent": cls["commercial_intent"],
                      "intent_confidence": cls["confidence"]}
            sc = score_keyword(merged)
            # Pure brand terms → Brand ad group, ranked highest (they convert best).
            is_brand_kw = kw["keyword"].lower() in brand_set
            intent = "brand" if is_brand_kw else cls["intent"]
            score = sc["score"] if kw.get("source") != "suggested" else max(sc["score"], 55.0)
            if is_brand_kw:
                score = max(score, 80.0)
            insights.append(
                {
                    "keyword": kw["keyword"],
                    "intent": intent,
                    "intent_confidence": cls["confidence"],
                    "score": round(score, 1),
                    "source": kw.get("source", "historical"),
                    "search_volume": kw.get("search_volume"),
                    "competition": kw.get("competition"),
                    "historical_clicks": kw.get("historical_clicks"),
                    "historical_ctr": kw.get("historical_ctr"),
                    "historical_cpc": kw.get("historical_cpc"),
                    "quality_score": kw.get("quality_score"),
                    "top_of_page_bid_low": kw.get("top_of_page_bid_low"),
                    "top_of_page_bid_high": kw.get("top_of_page_bid_high"),
                    "reason": f"{sc['reason']}. {cls['reason']}",
                    **recommend_bid(
                        {
                            "source": kw.get("source", "historical"),
                            "historical_cpc": kw.get("historical_cpc"),
                            "top_of_page_bid_low": kw.get("top_of_page_bid_low"),
                            "top_of_page_bid_high": kw.get("top_of_page_bid_high"),
                        }
                    ),
                    **recommend_match_type(
                        {
                            "intent": intent,
                            "historical_clicks": kw.get("historical_clicks"),
                            "historical_ctr": kw.get("historical_ctr"),
                        },
                        has_conversions=has_conversions,
                    ),
                }
            )
        insights.sort(key=lambda k: k["score"], reverse=True)
        insights = insights[:25]
        self._fill_bid_gaps(insights)
        return insights

    def _fill_bid_gaps(self, insights: list[dict[str, Any]]) -> None:
        """Give never-run keywords a starting bid from a per-intent benchmark.

        A keyword with no history or planner estimate would otherwise have no
        number. We fall back to the median recommended bid of its own intent
        group (else the overall median), so every keyword shows a concrete bid.
        """
        from statistics import median

        priced = [k["recommended_bid"] for k in insights if k.get("recommended_bid")]
        overall = round(median(priced)) if priced else None
        by_intent: dict[str, float] = {}
        for intent in {k["intent"] for k in insights}:
            vals = [
                k["recommended_bid"]
                for k in insights
                if k["intent"] == intent and k.get("recommended_bid")
            ]
            if vals:
                by_intent[intent] = round(median(vals))
        for k in insights:
            if k.get("recommended_bid"):
                continue
            bench = by_intent.get(k["intent"], overall)
            if bench:
                k["recommended_bid"] = float(bench)
                k["bid_basis"] = "benchmark"
                k["bid_reason"] = (
                    f"Never run before — start at ₹{bench} "
                    f"(median of your other {k['intent']} keywords)."
                )

    def _group_keywords(self, insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for k in insights:
            groups.setdefault(k["intent"], []).append(k)
        out: list[dict[str, Any]] = []
        for intent, items in groups.items():
            # Group default bid = median of the per-keyword recommended bids.
            from statistics import median
            bids = [i["recommended_bid"] for i in items if i.get("recommended_bid")]
            bid = round(median(bids)) if bids else None
            items = items[:12]
            kws = [i["keyword"] for i in items]
            # Paste-ready keywords, each in ITS OWN recommended match type
            # ('BOTH' expands to a phrase AND an exact entry).
            match_keywords: list[str] = []
            for i in items:
                match_keywords.extend(
                    _match_formats(i["keyword"], i.get("recommended_match_type", "PHRASE"))
                )
            # Distinct match types actually used in this group (for the header label).
            match_types = list(
                dict.fromkeys(i.get("recommended_match_type", "PHRASE") for i in items)
            )
            out.append(
                {
                    "name": f"{_titlecase(intent)} Intent",
                    "intent": intent,
                    "keywords": kws,
                    "recommended_match_types": match_types,
                    "recommended_bid": bid,
                    "match_keywords": match_keywords,
                }
            )
        # Brand ad group first, then the high-intent groups, then the rest.
        order = ["brand", "admission", "application", "registration", "deadline",
                 "fees", "course", "eligibility", "placement", "location"]
        out.sort(key=lambda g: (order.index(g["intent"]) if g["intent"] in order else 99))
        return out

    # ------------------------------------------------------------------ #
    # generation — LLM (hybrid) and deterministic backends
    # ------------------------------------------------------------------ #
    def _build_context(self, brief, landing, historical, keyword_insights, tone) -> dict[str, Any]:
        facts: list[str] = []
        fact_keys = (
            "courses", "placements", "scholarships", "accreditations", "deadlines", "rankings",
        )
        for key in fact_keys:
            facts.extend(landing.get(key, [])[:2])
        return {
            "brief": brief,
            "tone": tone,
            "landing_facts": facts[:12],
            "top_keywords": [k["keyword"] for k in keyword_insights[:12]],
            # Scored, intent-tagged keywords so generation can prioritise by funnel
            # stage (BOF/MOF) instead of treating every keyword equally.
            "top_insights": [
                {"keyword": k.get("keyword"), "intent": (k.get("intent") or "generic"),
                 "score": k.get("score") or 0, "search_volume": k.get("search_volume")}
                for k in keyword_insights[:15]
            ],
            "historical_headlines": historical["top_headlines"][:10],
            "historical_descriptions": historical["top_descriptions"][:6],
            "keyword_themes": historical["best_keyword_themes"][:10],
        }

    def _generate_assets(self, context: dict[str, Any]) -> tuple[dict[str, Any], str]:
        if self.llm.available():
            try:
                return self._llm_assets(context), "llm"
            except Exception as exc:  # any LLM problem → deterministic fallback
                log.info("ad_copy.llm_fallback", error=str(exc))
        return self._template_assets(context), "template"

    def _llm_assets(self, context: dict[str, Any]) -> dict[str, Any]:
        brief = context["brief"]
        system = (
            "You are a senior Google Ads strategist for university admissions. "
            "Write Responsive Search Ad copy grounded ONLY in the provided data. "
            "Never invent rankings, fees, or placement numbers. Headlines <=30 chars, "
            "descriptions <=90 chars. Return STRICT JSON only."
        )
        prompt = (
            f"Campus: {brief.brand} ({brief.location}). Programmes: {', '.join(brief.programs)}."
            + (f" Entrance exam: {brief.exam}." if brief.exam else "")
            + "\nTop keywords (real, use these intents directly): "
            + ", ".join(context["top_keywords"])
            + f"\nWinning historical headlines: {', '.join(context['historical_headlines'])}"
            + f"\nVerified landing-page facts: {', '.join(context['landing_facts']) or 'none'}"
            + (f"\nTone: {context['tone']}" if context.get("tone") else "")
            + "\nPRIORITISE bottom-of-funnel, high-intent messaging (brand, admission, "
            "application, apply/enrol, registration, the entrance exam, deadlines, the "
            "exact programme like MBA/PGDM/B.Tech) — these convert best, so most "
            "headlines should be these and include the brand name. Only write "
            "fees / eligibility / courses / placement headlines when those words "
            "actually appear in the top keywords above; do NOT add generic "
            "fees or eligibility slogans otherwise. Avoid generic slogans entirely."
            + "\nReturn JSON: {\"headlines\":[{\"text\":\"..\",\"reason\":\"..\"}] (15 items), "
            "\"descriptions\":[{\"text\":\"..\",\"reason\":\"..\"}] (4 items), "
            "\"callouts\":[\"..\"] (4 items)}. Each reason must cite the keyword it came from."
        )
        raw = self.llm.complete(system=system, prompt=prompt, max_tokens=2000)
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group())

        headlines = self._coerce_assets(data.get("headlines", []), H_MAX)
        descriptions = self._coerce_assets(data.get("descriptions", []), D_MAX)
        # Backfill from deterministic generator if the model under-delivered.
        if len(headlines) < 15 or len(descriptions) < 4:
            fallback = self._template_assets(context)
            headlines = (headlines + fallback["headlines"])[:15]
            descriptions = (descriptions + fallback["descriptions"])[:4]
        callouts = [c for c in (_fit(c, 25) for c in data.get("callouts", [])) if c][:4]
        return {"headlines": headlines[:15], "descriptions": descriptions[:4], "callouts": callouts}

    def _coerce_assets(self, items: list[Any], limit: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for it in items:
            if isinstance(it, dict):
                text, reason = it.get("text", ""), it.get("reason", "")
            else:
                text, reason = str(it), "Generated from campus data."
            fitted = _fit(text, limit)
            if fitted and fitted.lower() not in seen:
                seen.add(fitted.lower())
                out.append({"text": fitted, "length": len(fitted), "reason": reason,
                            "pinned_position": None})
        return out

    def _kw_headline(self, short: str, keyword: str) -> str | None:
        """Turn a real keyword into a clean, brand-cased headline (<=30 chars)."""
        h = _titlecase(keyword)
        # Force the brand's own casing (e.g. MICA not Mica).
        h = re.sub(rf"(?i)\b{re.escape(short)}\b", short, h)
        if short.lower() not in keyword.lower():
            h = f"{short} {h}"
        return _fit(h, H_MAX)

    def _template_assets(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deterministic generation driven by the campus's REAL keyword intents.

        Instead of fixed slogans, headlines/descriptions are built around the
        intents that actually appear in the account's top keywords (fees,
        courses, placements, online, programme, admission, exam), so the copy is
        specific to how people really search for this campus.
        """
        brief = context["brief"]
        s = brief.short
        loc = brief.location
        exam = brief.exam

        # Keep only brand-relevant terms — bid keywords first (cleanest), then any
        # brand-containing search terms. This drops broad-match spillover junk
        # ("ccc apply", "bursary application") that isn't about this campus.
        patterns = brief.patterns()

        def is_brand(kw: str) -> bool:
            low = kw.lower()
            return any(p in low for p in patterns)

        # Scored, intent-tagged keywords for this campus (brand-relevant only),
        # ranked by funnel tier then score so BOF high-intent keywords lead.
        insights = [
            k for k in context.get("top_insights", [])
            if k.get("keyword") and is_brand(k["keyword"])
        ]
        ranked = sorted(
            insights, key=lambda k: (_intent_tier(k.get("intent")), -(k.get("score") or 0))
        )
        present = {(k.get("intent") or "").lower() for k in insights}

        def has_intent(*names: str) -> bool:
            return any(n in present for n in names)

        # Text blob only for programme / scholarship / online detection (not intents).
        blob = " ".join(k["keyword"].lower() for k in insights) or " ".join(
            context.get("top_keywords", [])
        ).lower()
        f_fees = has_intent("fees")
        f_courses = has_intent("course", "courses")
        f_place = has_intent("placement")
        f_elig = has_intent("eligibility")
        f_schol = "scholarship" in blob
        f_online = ("online" in blob) or ("distance" in blob)
        progs = [
            p for p, kw in [("MBA", "mba"), ("PGDM", "pgdm"), ("B.Tech", "btech"),
                            ("BBA", "bba"), ("BCA", "bca"), ("LLB", "llb")] if kw in blob
        ]
        if not progs:  # fall back to the configured programme
            progs = [brief.programs[0]]

        # 1) Core bottom-of-funnel headlines — brand + apply/admission always lead
        #    (highest-converting), then programme-admission, exam, location.
        hl: list[tuple[str, str]] = [
            (s, "Brand headline — top relevance for brand searches (bottom-of-funnel)."),
            (f"Apply to {s} 2026", "Direct application CTA (bottom-of-funnel)."),
            (f"{s} Admission 2026", "Brand + 'admission' — a top converting intent."),
        ]
        for p in progs[:2]:
            hl.append((f"{s} {p} Admission", f"Programme ({p}) admission — high intent."))
        if exam:
            hl.append((f"{exam} Registration 2026", f"Entrance exam ({exam}) — bottom-of-funnel."))
            hl.append((f"Register for {exam} 2026", f"Exam registration ({exam})."))
        if loc:
            hl.append((f"{s} {loc} Admission", f"Brand + location ({loc})."))

        # 2) Headlines built VERBATIM from the real keywords, BOF first (ranked), so
        #    copy mirrors how people actually search for this campus.
        for k in ranked:
            kw = k["keyword"]
            h = self._kw_headline(s, kw)
            if not h:
                continue
            t = _intent_tier(k.get("intent"))
            stage = ("bottom-of-funnel" if t == 0 else "mid-of-funnel" if t == 1
                     else "top-of-funnel")
            hl.append((h, f"Built from your real keyword '{kw}' "
                          f"({k.get('intent')}, {stage})."))

        # 3) Mid-of-funnel headlines — ONLY when that intent genuinely ranks in the
        #    top keywords (never as generic filler).
        if f_fees:
            hl.append((f"{s} Fees & Courses", "'fees' ranks among your top keyword intents."))
            hl.append((f"{s} Fee Structure 2026", "Matches your 'fee structure' searches."))
        if f_courses:
            hl.append((f"{s} Courses & Programmes", "'courses' ranks among your top keywords."))
        if f_place:
            hl.append((f"{s} Placements & Careers", "'placement' ranks among your top keywords."))
        if f_online:
            hl.append((f"{s} Online Programmes", "'online/distance' ranks in your top keywords."))
        if f_elig:
            hl.append((f"{s} Eligibility & Cutoff", "'eligibility' ranks among your top keywords."))
        if f_schol:
            hl.append((f"{s} Scholarships 2026", "Scholarship intent in your keywords."))

        # 4) Brand / application top-ups (bottom-of-funnel — NOT generic fees or
        #    eligibility) to reach 15 headlines.
        study = f"Study at {s}, {loc}" if loc else f"Study at {s}"
        hl += [
            (f"{s} Admissions 2026", "Brand + admissions + year."),
            (f"{s} {progs[0]} 2026", f"Brand + programme ({progs[0]})."),
            (f"{s} Application Form 2026", "Application-form intent (bottom-of-funnel)."),
            (f"Apply Online to {s}", "Apply-online CTA."),
            (study, f"Brand{' + location' if loc else ''} awareness."),
            (f"{s} Official Admissions", "Brand + trust signal."),
            ("Admissions Open 2026", "Open-now signal."),
            ("Enquire About Admissions", "Soft-conversion CTA."),
            ("Applications Closing Soon", "Deadline urgency (bottom-of-funnel)."),
        ]

        headlines: list[dict[str, Any]] = []
        seen: set[str] = set()
        for text, reason in hl:
            fitted = _fit(text, H_MAX)
            if fitted and fitted.lower() not in seen:
                seen.add(fitted.lower())
                headlines.append({"text": fitted, "length": len(fitted), "reason": reason,
                                  "pinned_position": 1 if fitted == s else None})
            if len(headlines) >= 15:
                break

        # Descriptions weave in the SAME real intents.
        detail_bits = []
        if f_courses or f_fees:
            detail_bits.append("courses & fees")
        if f_place:
            detail_bits.append("placements")
        if f_schol:
            detail_bits.append("scholarships")
        detail = ", ".join(detail_bits[:3]) or "programmes, fees & placements"
        prog0 = progs[0]

        dl: list[tuple[str, str]] = [
            (f"Apply to {s} for 2026. Get {detail} & admission details. Enquire online now.",
             f"Admission + real intents ({detail})."),
            (f"{s} admissions open. Check {'fees, ' if f_fees else ''}courses "
             f"& eligibility. Apply today.",
             "Admission + fees/courses/eligibility intents."),
            (f"Join {prog0} at {s}. {'Strong placements. ' if f_place else ''}"
             f"Apply for the 2026 batch now.",
             f"Programme ({prog0}) + placement intent."),
            (f"Looking for {s} {'fees & ' if f_fees else ''}admission details? "
             f"Apply online for 2026.",
             "Question hook around fees/admission searches."),
            (f"Register for {exam} 2026 & apply to {s}. Dates, eligibility & fees inside.",
             f"Exam ({exam}) path.") if exam else
            (f"{s} 2026 admissions. Explore {detail} and apply online in minutes.",
             "Admission + real intents."),
        ]
        descriptions: list[dict[str, Any]] = []
        seen_d: set[str] = set()
        for text, reason in dl:
            fitted = _fit(text, D_MAX)
            if fitted and fitted.lower() not in seen_d:
                seen_d.add(fitted.lower())
                descriptions.append({"text": fitted, "length": len(fitted), "reason": reason,
                                     "pinned_position": None})
            if len(descriptions) >= 4:
                break

        return {"headlines": headlines, "descriptions": descriptions, "callouts": []}

    # ------------------------------------------------------------------ #
    # structural assets (data-derived)
    # ------------------------------------------------------------------ #
    def _paths(self, brief, keyword_insights) -> list[str]:
        paths = ["Admissions", brief.programs[0].replace(".", "").replace("-", "")[:15]]
        return [p[:15] for p in paths if p][:2]

    def _callouts(self, brief, landing) -> list[str]:
        base = ["Admissions Open 2026", "Apply Online", "Scholarships Available", "Limited Seats"]
        if landing.get("placements"):
            base.insert(0, "Placement Support")
        return [c for c in (_fit(c, 25) for c in base) if c][:4]

    def _snippets(self, brief, landing) -> dict[str, list[str]]:
        snippets = {"Programs": brief.programs[:]}
        courses = [re.sub(r"\s+", " ", c)[:25] for c in landing.get("courses", [])[:4]]
        if courses:
            snippets["Courses"] = courses
        return snippets

    def _sitelinks(self, brief, selected) -> list[dict[str, Any]]:
        url = selected["url"] if selected else (brief.homepage or "")
        # Google Ads sitelinks: text ≤25 chars, two optional descriptions ≤35 chars each.
        items = [
            ("Apply Online", "Start your application", "Quick online form — apply now"),
            ("Admissions 2026", "2026 intake now open", "Check dates & eligibility"),
            ("Courses & Fees", "Explore programmes & fees", "Compare specialisations"),
            ("Contact / Enquire", "Talk to an admissions expert", "Get a callback today"),
        ]
        return [
            {
                "text": (_fit(t, 25) or t[:25]),
                "description1": _fit(d1, 35),
                "description2": _fit(d2, 35),
                "final_url": url,
            }
            for t, d1, d2 in items
        ]

    def _campaign_recommendation(self, brief, keyword_groups) -> dict[str, Any]:
        ag = [g["name"] for g in keyword_groups[:6]] or ["Brand", "Admissions", "Application"]
        return {
            "campaign_name": f"{brief.short} | Admissions 2026 | Search",
            "ad_group_suggestions": ag,
            "device_strategy": (
                "Prioritise mobile (majority of admissions traffic); keep desktop bid parity."
            ),
            "geo_strategy": (
                f"Target {brief.location or 'key metros'} + India-wide for brand terms."
            ),
            "ad_schedule": "All week; increase bids evenings & weekends when enquiries peak.",
            "audience_observation": (
                "Add 'in-market: higher education' as observation (not targeting) to learn."
            ),
            "structure_notes": [
                "One ad group per intent (brand / admission / application / course).",
                "Pin the brand headline to position 1 on brand ad groups.",
                "Use the negative list to block job/result/free queries.",
            ],
        }

    # ------------------------------------------------------------------ #
    def _persist(self, brief, account_id, actor, selected, backend, historical,
                 keyword_insights, assets, quality, result) -> int | None:
        try:
            row = self.repo.record(
                {
                    "actor": actor,
                    "campus": brief.brand,
                    "account_id": account_id,
                    "final_url": selected["url"] if selected else None,
                    "url_source": selected["source"] if selected else None,
                    "url_confidence": selected["confidence"] if selected else None,
                    "backend": backend,
                    "historical_features_used": {
                        "top_headlines": historical["top_headlines"][:10],
                        "keyword_themes": historical["best_keyword_themes"],
                        "avg_ctr": historical["avg_ctr"],
                        "avg_cpc": historical["avg_cpc"],
                    },
                    "keyword_snapshot": {
                        "keywords": keyword_insights[:25],
                        "groups": result.get("keyword_groups", []),
                    },
                    "generated_assets": assets,
                    "scores": {
                        "quality": quality,
                        "campaign_plan": result.get("campaign_plan"),
                        "seasonality": result.get("seasonality"),
                        "keyword_history": result.get("keyword_history"),
                        "top_search_terms": result.get("top_search_terms"),
                        "setup_guide": result.get("setup_guide"),
                        "negative_keywords_detail": result.get("negative_keywords_detail"),
                        "landing_quality": result.get("landing_quality"),
                        "landing_audit": result.get("landing_audit"),
                    },
                    "reasoning": {
                        "headlines": [{"text": a["text"], "reason": a["reason"]}
                                      for a in assets["headlines"]],
                        "descriptions": [{"text": a["text"], "reason": a["reason"]}
                                         for a in assets["descriptions"]],
                    },
                    # Full result payload (JSON-safe) so the plan can be re-opened
                    # exactly as generated. default=str coerces datetimes/Decimals.
                    "result_payload": json.loads(json.dumps(result, default=str)),
                }
            )
            self.db.commit()
            return row.id
        except Exception as exc:  # persistence must never break generation
            log.info("ad_copy.persist_failed", error=str(exc))
            self.db.rollback()
            return None
