"""Automated Responsive Search Ad (RSA) copy generator.

Reads each campaign's historical winning keywords + search terms from the
database and generates Google-Ads-compliant RSA assets:

  * up to 15 headlines  (<= 30 characters each)
  * up to 4  descriptions (<= 90 characters each)
  * suggested new keywords (from high-intent search terms)
  * suggested negative keywords

Two generation backends:
  * ``template``  - deterministic, data-grounded copy (no external API; default)
  * ``llm``       - Anthropic Claude, used automatically when ANTHROPIC_API_KEY
                    is set, for richer variation (falls back to template on error)

Run:  .venv/Scripts/python -m scripts.adcopy_generator            (all 5)
      .venv/Scripts/python -m scripts.adcopy_generator --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.database.session import engine

H_MAX = 30  # RSA headline character limit
D_MAX = 90  # RSA description character limit


# --------------------------------------------------------------------------- #
# Per-campaign brief (brand facts + the DB name filter to pull history)
# --------------------------------------------------------------------------- #
@dataclass
class Brief:
    key: str
    brand: str
    short: str
    location: str
    programs: list[str]
    exam: str | None
    sql_filter: str
    # enriched from the DB at runtime:
    top_terms: list[str] = field(default_factory=list)
    top_keywords: list[str] = field(default_factory=list)


BRIEFS: list[Brief] = [
    Brief("indus", "Indus University", "Indus", "Ahmedabad", ["B.Tech", "Admissions"], None,
          "(c.name ILIKE '%indus%' AND c.name NOT ILIKE '%hindus%')"),
    Brief("gibs", "GIBS Business School", "GIBS", "Bangalore", ["PGDM", "MBA"], None,
          "(c.name ILIKE '%gibs%')"),
    Brief("nmims", "NMIMS", "NMIMS", "Mumbai", ["MBA", "NPAT"], "NMAT",
          "(c.name ILIKE '%nmims%' OR c.name ILIKE '%nmat%')"),
    Brief("mica", "MICA", "MICA", "Ahmedabad", ["PGDM-C", "MBA"], "MICAT",
          "(c.name ILIKE '%mica%')"),
    Brief("gim", "Goa Institute of Management", "GIM", "Goa", ["PGDM", "MBA"], None,
          "(c.name ILIKE '%goa institute%' OR c.name ~* '\\ygim\\y')"),
]

STOPWORDS = {"the", "in", "of", "for", "and", "2025", "2026", "admission", "admissions"}


def enrich(brief: Brief) -> None:
    """Pull the brand's top search terms + keywords (by spend) from the DB."""
    with engine.connect() as db:
        brief.top_terms = [
            r[0] for r in db.execute(text(f"""
                SELECT st.query FROM search_term_snapshots sts
                JOIN search_terms st ON sts.search_term_id = st.id
                JOIN campaigns c ON sts.campaign_id = c.id
                WHERE {brief.sql_filter}
                GROUP BY st.query ORDER BY sum(sts.cost_micros) DESC LIMIT 15
            """)).all()
        ]
        brief.top_keywords = [
            r[0] for r in db.execute(text(f"""
                SELECT k.text FROM keyword_snapshots ks
                JOIN keywords k ON ks.keyword_id = k.id
                JOIN campaigns c ON ks.campaign_id = c.id
                WHERE {brief.sql_filter}
                GROUP BY k.text ORDER BY sum(ks.cost_micros) DESC LIMIT 15
            """)).all()
        ]


# --------------------------------------------------------------------------- #
# Template backend (deterministic, always available)
# --------------------------------------------------------------------------- #
def _fit(s: str, limit: int) -> str | None:
    s = re.sub(r"\s+", " ", s).strip(" -|")
    return s if 1 <= len(s) <= limit else None


def _dedupe(seq: list[str]) -> list[str]:
    seen, out = set(), []
    for s in seq:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _title(term: str) -> str:
    return " ".join(w.capitalize() for w in term.split())


def generate_template(b: Brief) -> dict[str, Any]:
    prog = b.programs[0]
    # Headline candidates, ordered by priority; each validated to <= 30 chars.
    hl = [
        b.brand,
        f"{b.short} Admissions 2026",
        f"Apply to {b.short} 2026",
        f"{b.short} — Apply Online",
        f"{prog} at {b.short}",
        f"{b.short} {prog} Program",
        f"Admissions Open 2026",
        f"{b.short} Application Form",
        f"Study at {b.short}, {b.location}",
        f"Top College in {b.location}",
        "Limited Seats — Apply Now",
        "Book Your Seat Today",
        "Check Eligibility & Apply",
        "Scholarships Available",
        "Placement Assistance",
        "Enquire About Admissions",
        "Applications Closing Soon",
        f"{b.short} Official Admissions",
    ]
    if b.exam:
        hl[7:7] = [f"{b.exam} Registration Open", f"Register for {b.exam} 2026"]
    # Enrich with a couple of proven query themes (Title-cased), if they fit.
    for term in b.top_terms[:4]:
        cand = _title(term)
        if "form" in term or "apply" in term or "admission" in term:
            hl.append(cand)

    headlines = _dedupe([h for h in (_fit(x, H_MAX) for x in hl) if h])[:15]

    desc = [
        f"Apply to {b.brand} for 2026 admissions. Explore programs, fees & scholarships now.",
        f"{b.short} admissions are open. Fill the online application form in minutes today.",
        f"Study {prog} at {b.short}, {b.location}. Placement support & scholarships. Apply now.",
        f"Take the next step in your career at {b.short}. Check eligibility & apply online.",
        f"Limited seats for the 2026 batch at {b.short}. Enquire today & secure your admission.",
    ]
    if b.exam:
        desc.insert(1, f"Register for {b.exam} 2026 & apply to {b.short}. Guidance, dates & eligibility inside.")
    descriptions = _dedupe([d for d in (_fit(x, D_MAX) for x in desc) if d])[:4]

    # New-keyword ideas: high-intent search terms not already exact keywords.
    kw_lower = {k.lower() for k in b.top_keywords}
    suggested_keywords = [t for t in b.top_terms if t.lower() not in kw_lower][:8]
    negatives = ["free", "jobs", "salary", "result", "fees refund", "scholarship exam", "sample paper"]

    return {
        "backend": "template",
        "headlines": headlines,
        "descriptions": descriptions,
        "suggested_keywords": suggested_keywords,
        "suggested_negatives": negatives,
    }


# --------------------------------------------------------------------------- #
# Optional LLM backend (Anthropic Claude) — used only if a key is configured
# --------------------------------------------------------------------------- #
def generate_llm(b: Brief) -> dict[str, Any] | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    prompt = (
        f"You are a Google Ads copywriter. Write Responsive Search Ad copy for "
        f"{b.brand} ({b.location}) promoting {', '.join(b.programs)} admissions for 2026.\n"
        f"Top-performing search terms (from real data): {', '.join(b.top_terms[:10])}.\n"
        "Return STRICT JSON with keys 'headlines' (exactly 15 strings, each <=30 chars) and "
        "'descriptions' (exactly 4 strings, each <=90 chars). No claims that can't be verified "
        "(no fake rankings/placement numbers). Include the brand, program, a clear CTA, and 2026."
    )
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-sonnet-5", max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group())
        return {
            "backend": "llm",
            "headlines": [h for h in (_fit(x, H_MAX) for x in data["headlines"]) if h][:15],
            "descriptions": [d for d in (_fit(x, D_MAX) for x in data["descriptions"]) if d][:4],
            "suggested_keywords": b.top_terms[:8],
            "suggested_negatives": ["free", "jobs", "salary", "result"],
        }
    except Exception:
        return None


def generate(b: Brief) -> dict[str, Any]:
    enrich(b)
    return generate_llm(b) or generate_template(b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full output to this JSON path")
    args = ap.parse_args()

    result = {}
    for b in BRIEFS:
        out = generate(b)
        result[b.brand] = out
        print(f"\n{'='*70}\n{b.brand}  ({b.location})   [backend: {out['backend']}]\n{'='*70}")
        print(f"-- HEADLINES ({len(out['headlines'])}/15) --")
        for h in out["headlines"]:
            print(f"  [{len(h):2d}] {h}")
        print(f"-- DESCRIPTIONS ({len(out['descriptions'])}/4) --")
        for d in out["descriptions"]:
            print(f"  [{len(d):2d}] {d}")
        if out["suggested_keywords"]:
            print("-- NEW KEYWORD IDEAS --  " + " · ".join(out["suggested_keywords"][:6]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved -> {args.json}")


if __name__ == "__main__":
    main()
