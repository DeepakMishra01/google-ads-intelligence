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
from app.repositories.ad_copy import AdCopyRepository
from app.services.ai import intent_classifier
from app.services.ai.campus_config import find_brief, generic_brief
from app.services.ai.campus_service import CampusService
from app.services.ai.historical_intelligence_service import HistoricalIntelligenceService
from app.services.ai.keyword_research_service import KeywordResearchService
from app.services.ai.keyword_scorer import score_keyword
from app.services.ai.landing_page_service import LandingPageService
from app.services.ai.rsa_validator import D_MAX, H_MAX, validate_assets

log = get_logger(__name__)

_NEGATIVES = [
    "free", "jobs", "job", "salary", "result", "sample paper", "wikipedia", "pdf download",
]
_MATCH_BY_INTENT = {
    "brand": ["EXACT", "PHRASE"],
    "deadline": ["PHRASE", "EXACT"],
    "application": ["PHRASE", "EXACT"],
    "registration": ["PHRASE", "EXACT"],
    "admission": ["PHRASE", "EXACT"],
    "fees": ["PHRASE"],
    "eligibility": ["PHRASE"],
    "course": ["PHRASE", "BROAD"],
    "placement": ["PHRASE"],
    "location": ["PHRASE"],
    "informational": ["BROAD"],
}


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


class AdCopyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.campus = CampusService(db)
        self.landing = LandingPageService(db)
        self.history = HistoricalIntelligenceService(db)
        self.keywords = KeywordResearchService(db)
        self.repo = AdCopyRepository(db)
        self.llm = get_llm_client()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def search_campus(self, q: str | None, *, limit: int = 10) -> dict[str, Any]:
        return {"items": self.campus.search(q, limit=limit)}

    def discover_url(self, campus: str, *, override: str | None = None) -> dict[str, Any]:
        brief = find_brief(campus) or generic_brief(campus)
        return self.campus.discover_final_url(brief, override=override)

    def generate(
        self,
        *,
        campus: str,
        account_id: int | None = None,
        final_url: str | None = None,
        tone: str | None = None,
        persist: bool = True,
        actor: str | None = None,
    ) -> dict[str, Any]:
        brief = find_brief(campus) or generic_brief(campus)

        # Step 2: Final URL.
        url_result = self.campus.discover_final_url(brief, override=final_url)
        selected = url_result["selected"]

        # Step 3: landing page.
        landing = self.landing.analyze(selected["url"] if selected else None)

        # Step 4: historical intelligence.
        historical = self.history.analyze(brief)

        # Steps 5-7: keyword research → intent → scoring.
        raw_kw, providers_used = self.keywords.collect(brief)
        keyword_insights = self._score_keywords(brief, raw_kw)
        keyword_groups = self._group_keywords(keyword_insights)

        # Step 9: generation (hybrid LLM → deterministic fallback).
        context = self._build_context(brief, landing, historical, keyword_insights, tone)
        assets, backend = self._generate_assets(context)

        # Structural assets are data-derived (grounded, not invented).
        assets["display_paths"] = self._paths(brief, keyword_insights)
        assets["callouts"] = assets.get("callouts") or self._callouts(brief, landing)
        assets["structured_snippets"] = self._snippets(brief, landing)
        assets["sitelinks"] = self._sitelinks(brief, selected)
        assets["negative_keywords"] = self._negatives(historical)

        # Step 10: validation + quality prediction.
        quality = validate_assets(
            headlines=[a["text"] for a in assets["headlines"]],
            descriptions=[a["text"] for a in assets["descriptions"]],
            display_paths=assets["display_paths"],
            callouts=assets["callouts"],
            keyword_themes=historical["best_keyword_themes"] or brief.programs,
        )

        recommendation = self._campaign_recommendation(brief, keyword_groups)

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
            "generated_at": datetime.now(UTC),
            "providers_used": providers_used,
        }

        gen_id = None
        if persist:
            gen_id = self._persist(brief, account_id, actor, selected, backend, historical,
                                   keyword_insights, assets, quality, result)
        result["id"] = gen_id
        return result

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

    # ------------------------------------------------------------------ #
    # keyword scoring + grouping
    # ------------------------------------------------------------------ #
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

    def _score_keywords(self, brief, raw_kw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        patterns = brief.patterns()

        def is_relevant(kw: str) -> bool:
            return any(p in kw.lower() for p in patterns)

        # Drop broad-match spillover: keep only keywords that mention this campus.
        historical = [kw for kw in raw_kw if is_relevant(kw["keyword"])]
        # Merge the generated brand plan for coverage (dedupe by text).
        seen = {kw["keyword"].lower() for kw in historical}
        candidates = historical + [
            p for p in self._keyword_plan(brief) if p["keyword"].lower() not in seen
        ]

        brand_terms = brief.patterns()
        insights: list[dict[str, Any]] = []
        for kw in candidates:
            cls = intent_classifier.classify(kw["keyword"], brand_terms=brand_terms)
            merged = {**kw, "commercial_intent": cls["commercial_intent"],
                      "intent_confidence": cls["confidence"]}
            sc = score_keyword(merged)
            # Suggested keywords have no metrics; give them a relevance floor so a
            # clean brand plan still surfaces above nothing.
            score = sc["score"] if kw.get("source") != "suggested" else max(sc["score"], 55.0)
            insights.append(
                {
                    "keyword": kw["keyword"],
                    "intent": cls["intent"],
                    "intent_confidence": cls["confidence"],
                    "score": round(score, 1),
                    "source": kw.get("source", "historical"),
                    "search_volume": kw.get("search_volume"),
                    "competition": kw.get("competition"),
                    "historical_clicks": kw.get("historical_clicks"),
                    "historical_ctr": kw.get("historical_ctr"),
                    "historical_cpc": kw.get("historical_cpc"),
                    "quality_score": kw.get("quality_score"),
                    "reason": f"{sc['reason']}. {cls['reason']}",
                }
            )
        insights.sort(key=lambda k: k["score"], reverse=True)
        return insights[:25]

    def _group_keywords(self, insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for k in insights:
            groups.setdefault(k["intent"], []).append(k)
        out: list[dict[str, Any]] = []
        for intent, items in groups.items():
            cpcs = [i["historical_cpc"] for i in items if i.get("historical_cpc")]
            bid = round(sum(cpcs) / len(cpcs), 2) if cpcs else None
            kws = [i["keyword"] for i in items][:12]
            match_types = _MATCH_BY_INTENT.get(intent, ["PHRASE"])
            # Paste-ready keywords in Google Ads match-type syntax.
            match_keywords = [_match_format(k, mt) for k in kws for mt in match_types]
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
        out.sort(key=lambda g: len(g["keywords"]), reverse=True)
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
            + "\nMost headlines MUST reflect the specific intents in the top keywords "
            "(e.g. fees, fee structure, courses, placements, the exact programme like "
            "MBA/PGDM/B.Tech, online, admission, application form, the entrance exam) — "
            "not generic slogans. Include the brand name in most headlines."
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

        ordered = list(dict.fromkeys([*context["keyword_themes"], *context["top_keywords"]]))
        brand_kw = [kw for kw in ordered if is_brand(kw)]
        # Intent detection uses brand-relevant keywords (fall back to all if none).
        blob = " ".join(brand_kw or ordered).lower()

        def has(*ws: str) -> bool:
            return any(w in blob for w in ws)

        f_fees = has("fee")
        f_courses = has("course")
        f_place = has("placement")
        f_online = has("online", "distance")
        f_admit = has("admission")
        f_elig = has("eligibility", "eligible", "cutoff", "cut off")
        f_schol = has("scholarship")
        progs = [
            p for p, kw in [("MBA", "mba"), ("PGDM", "pgdm"), ("B.Tech", "btech"),
                            ("BBA", "bba"), ("BCA", "bca"), ("LLB", "llb")] if kw in blob
        ]
        if not progs:  # fall back to the configured programme
            progs = [brief.programs[0]]

        # Candidate headlines, ranked: brand → real programme/intent → exam/location → CTA.
        hl: list[tuple[str, str]] = [
            (s, "Brand headline — top relevance for brand searches."),
            (f"{s} Admission 2026", "Brand + 'admission' — a top keyword intent."),
            (f"Apply to {s} 2026", "Direct application CTA."),
        ]
        for p in progs[:2]:
            hl.append((f"{s} {p} Admission", f"'{p}' appears in your top keywords."))
        if f_fees:
            hl.append((f"{s} Fees & Courses", "'fees' is your most-searched intent."))
            hl.append((f"{s} Fee Structure 2026", "Matches 'fee structure' searches."))
        if f_courses:
            hl.append((f"{s} Courses & Programmes", "'courses' is a top keyword intent."))
        if f_place:
            hl.append((f"{s} Placements & Careers", "'placement' is a top keyword intent."))
        if f_online:
            hl.append((f"{s} Online Programmes", "'online/distance' is a top keyword intent."))
        if f_admit:
            hl.append((f"{s} Application Form 2026", "Matches 'application form' searches."))
        if exam:
            hl.append((f"{exam} Registration 2026", f"Entrance exam ({exam}) intent."))
            hl.append((f"Register for {exam} 2026", f"Exam registration ({exam})."))
        if loc:
            hl.append((f"{s} {loc} Admission", f"Brand + location ({loc}) — your keyword style."))
        if f_elig:
            hl.append((f"{s} Eligibility & Cutoff", "Eligibility/cutoff intent."))
        if f_schol:
            hl.append((f"{s} Scholarships 2026", "Scholarship intent."))
        # A few built verbatim from the top BRAND keywords (authentic phrasing).
        for kw in brand_kw[:6]:
            h = self._kw_headline(s, kw)
            if h:
                hl.append((h, f"Built directly from your real keyword '{kw}'."))
        # Brand + generic fallbacks to top up to 15 (used only if needed).
        study = f"Study at {s}, {loc}" if loc else f"Study at {s}"
        hl += [
            (f"{s} Admissions 2026", "Brand + admissions + year."),
            (f"{s} {progs[0]} 2026", f"Brand + programme ({progs[0]})."),
            (f"{s} Application Form", "Application-form intent."),
            (study, f"Brand{' + location' if loc else ''} awareness."),
            (f"Apply Online to {s}", "Apply-online CTA."),
            (f"{s} Official Admissions", "Brand + trust signal."),
            ("Admissions Open 2026", "Open-now signal."),
            ("Check Eligibility & Apply", "Eligibility → apply."),
            ("Enquire About Admissions", "Soft-conversion CTA."),
            ("Applications Closing Soon", "Deadline urgency."),
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
        titles = ["Apply Online", "Admissions 2026", "Courses & Fees", "Contact / Enquire"]
        return [
            {"text": t, "description1": None, "description2": None, "final_url": url}
            for t in titles
        ]

    def _negatives(self, historical) -> list[str]:
        return list(dict.fromkeys(_NEGATIVES))

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
                    "scores": {"quality": quality},
                    "reasoning": {
                        "headlines": [{"text": a["text"], "reason": a["reason"]}
                                      for a in assets["headlines"]],
                        "descriptions": [{"text": a["text"], "reason": a["reason"]}
                                         for a in assets["descriptions"]],
                    },
                }
            )
            self.db.commit()
            return row.id
        except Exception as exc:  # persistence must never break generation
            log.info("ad_copy.persist_failed", error=str(exc))
            self.db.rollback()
            return None
