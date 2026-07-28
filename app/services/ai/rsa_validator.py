"""RSA validation + quality prediction (Step 10).

Checks generated assets against Google's hard limits and best-practice signals,
then predicts Ad Strength. Pure functions over the asset lists — no external
calls — so it's fast and unit-testable.
"""

from __future__ import annotations

import re
from typing import Any

H_MAX = 30
D_MAX = 90
PATH_MAX = 15
CALLOUT_MAX = 25


def _flag(level: str, field: str, message: str) -> dict[str, str]:
    return {"level": level, "field": field, "message": message}


def validate_assets(
    *,
    headlines: list[str],
    descriptions: list[str],
    display_paths: list[str] | None = None,
    callouts: list[str] | None = None,
    keyword_themes: list[str] | None = None,
) -> dict[str, Any]:
    display_paths = display_paths or []
    callouts = callouts or []
    keyword_themes = keyword_themes or []
    flags: list[dict[str, str]] = []

    # --- hard character limits ---
    for h in headlines:
        if len(h) > H_MAX:
            flags.append(_flag("error", "headline", f"'{h}' exceeds {H_MAX} chars ({len(h)})."))
    for d in descriptions:
        if len(d) > D_MAX:
            flags.append(_flag("error", "description", f"'{d}' exceeds {D_MAX} chars ({len(d)})."))
    for p in display_paths:
        if len(p) > PATH_MAX:
            flags.append(_flag("error", "path", f"Path '{p}' exceeds {PATH_MAX} chars."))
    for c in callouts:
        if len(c) > CALLOUT_MAX:
            flags.append(_flag("warning", "callout", f"Callout '{c}' exceeds {CALLOUT_MAX} chars."))

    # --- minimum counts (Google requires 3 headlines + 2 descriptions) ---
    if len(headlines) < 3:
        flags.append(_flag("error", "headline", "Fewer than 3 headlines."))
    if len(descriptions) < 2:
        flags.append(_flag("error", "description", "Fewer than 2 descriptions."))
    if len(headlines) < 11:
        flags.append(
            _flag("info", "headline", "Add more headlines (15 recommended for best Ad Strength).")
        )
    if len(descriptions) < 4:
        flags.append(_flag("info", "description", "Add up to 4 descriptions for best Ad Strength."))

    # --- duplicates / diversity ---
    lower_h = [h.lower() for h in headlines]
    dupes = {h for h in lower_h if lower_h.count(h) > 1}
    for d in dupes:
        flags.append(_flag("warning", "headline", f"Duplicate headline: '{d}'."))
    unique_ratio = (len(set(lower_h)) / len(lower_h)) if lower_h else 0.0

    # --- ALL CAPS / punctuation / stuffing ---
    for h in headlines:
        letters = re.sub(r"[^a-zA-Z]", "", h)
        if letters and letters.isupper() and len(letters) > 3:
            flags.append(_flag("warning", "headline", f"Excessive capitalisation: '{h}'."))
        if "!!" in h or "  " in h:
            flags.append(_flag("warning", "headline", f"Punctuation/spacing issue: '{h}'."))
        words = [w for w in re.findall(r"[a-zA-Z]+", h.lower()) if len(w) > 2]
        if words and max(words.count(w) for w in set(words)) >= 3:
            flags.append(_flag("warning", "headline", f"Possible keyword stuffing: '{h}'."))

    # --- keyword coverage: do headlines reflect winning themes? ---
    theme_tokens = {
        t for kw in keyword_themes for t in re.findall(r"[a-zA-Z]{3,}", kw.lower())
    }
    hay = " ".join(lower_h)
    covered = sum(1 for t in theme_tokens if t in hay)
    coverage = (covered / len(theme_tokens)) if theme_tokens else 0.0

    quality = _predict_strength(
        headlines=headlines,
        descriptions=descriptions,
        unique_ratio=unique_ratio,
        coverage=coverage,
        error_count=sum(1 for f in flags if f["level"] == "error"),
        flags=flags,
    )
    return quality


def _predict_strength(
    *,
    headlines: list[str],
    descriptions: list[str],
    unique_ratio: float,
    coverage: float,
    error_count: int,
    flags: list[dict[str, str]],
) -> dict[str, Any]:
    # Simple additive model over the signals Google's Ad Strength rewards.
    points = 0
    points += min(4, len(headlines) // 4)          # up to 4 for headline volume
    points += min(2, len(descriptions))            # up to 2 for descriptions
    points += 2 if unique_ratio >= 0.9 else (1 if unique_ratio >= 0.7 else 0)
    points += 2 if coverage >= 0.5 else (1 if coverage >= 0.25 else 0)
    if error_count:
        points = max(0, points - 3)

    if error_count:
        strength = "POOR"
    elif points >= 8:
        strength = "EXCELLENT"
    elif points >= 6:
        strength = "GOOD"
    elif points >= 4:
        strength = "AVERAGE"
    else:
        strength = "POOR"

    ctr_band = {
        "EXCELLENT": "above average",
        "GOOD": "average to above average",
        "AVERAGE": "around average",
        "POOR": "below average",
    }[strength]
    qs_contrib = {
        "EXCELLENT": "strong positive (ad relevance + expected CTR)",
        "GOOD": "positive",
        "AVERAGE": "neutral",
        "POOR": "at risk — fix errors before launch",
    }[strength]

    return {
        "expected_ad_strength": strength,
        "headline_count": len(headlines),
        "description_count": len(descriptions),
        "unique_headline_ratio": round(unique_ratio, 3),
        "keyword_coverage": round(coverage, 3),
        "predicted_ctr_band": ctr_band,
        "quality_score_contribution": qs_contrib,
        "flags": flags,
    }
