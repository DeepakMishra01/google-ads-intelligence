"""Tests for per-keyword match types and the negative-keyword theme detector.

Match-type rules must protect budget: brand & proven → Exact, high-intent → Phrase,
Broad only with conversion tracking. Negatives must flag real waste (jobs, results,
logins) but never a genuine on-brand query.
"""

from __future__ import annotations

from app.services.ai.keyword_scorer import recommend_match_type
from app.services.ai.negative_keywords_service import _COMPILED


# ------------------------------ match types ------------------------------- #
def test_brand_is_exact():
    r = recommend_match_type({"intent": "brand"})
    assert r["recommended_match_type"] == "EXACT"


def test_proven_performer_is_exact():
    r = recommend_match_type(
        {"intent": "admission", "historical_clicks": 120, "historical_ctr": 0.22}
    )
    assert r["recommended_match_type"] == "EXACT"
    assert "Proven" in r["match_reason"]


def test_high_intent_new_keyword_is_phrase():
    r = recommend_match_type({"intent": "application", "historical_clicks": 0})
    assert r["recommended_match_type"] == "PHRASE"


def test_broad_only_with_conversion_tracking():
    kw = {"intent": "course", "historical_clicks": 80, "historical_ctr": 0.05}
    assert recommend_match_type(kw, has_conversions=False)["recommended_match_type"] != "BROAD"
    assert recommend_match_type(kw, has_conversions=True)["recommended_match_type"] == "BROAD"


def test_low_data_defaults_to_phrase_not_broad():
    r = recommend_match_type({"intent": "fees"}, has_conversions=False)
    assert r["recommended_match_type"] == "PHRASE"
    assert "Broad" in r["match_reason"]  # explains why not broad


# --------------------------- negative themes ------------------------------ #
def _theme_for(query: str) -> str | None:
    for theme, _word, rx in _COMPILED:
        if rx.search(query.lower()):
            return theme
    return None


def test_job_seekers_flagged():
    assert _theme_for("indus university jobs") == "job seekers"
    assert _theme_for("indus university recruitment 2026") == "job seekers"


def test_result_and_admit_card_flagged():
    assert _theme_for("indus university result") == "exam result / admit card"
    assert _theme_for("nmat admit card download") == "exam result / admit card"


def test_login_and_pdf_flagged():
    assert _theme_for("indus student login") == "current students (not prospects)"
    assert _theme_for("indus university brochure pdf") == "info only / non-applicants"


def test_genuine_admission_query_not_flagged():
    # The whole point: real intent queries must survive.
    assert _theme_for("indus university admission 2026") is None
    assert _theme_for("indus university application form") is None
    assert _theme_for("indus university fees") is None
