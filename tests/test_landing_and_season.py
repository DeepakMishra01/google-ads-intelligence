"""Tests for landing-page quality scoring and admission-season pacing."""

from __future__ import annotations

from app.services.ai.budget_planner import _season_weights, build_plan
from app.services.ai.landing_quality import score_landing_page


# --------------------------- landing quality ------------------------------ #
def test_landing_unavailable_when_not_fetched():
    assert score_landing_page({"fetched": False})["available"] is False


def test_landing_scores_and_flags_only_real_gaps():
    landing = {
        "fetched": True,
        "cta_buttons": ["Apply Now"],
        "fees": ["Tuition ₹2L/yr"],
        "courses": ["MBA", "BBA"],
        "deadlines": ["Last date 31 July"],
        "placements": [],           # missing → should be suggested
        "accreditations": [],       # missing → should be suggested
        "rankings": [],
        "h1": ["Admissions 2026"],
        "meta_title": "X", "meta_description": "Y",
        "scholarships": [],         # missing → should be suggested
    }
    r = score_landing_page(landing, mobile_heavy=True)
    assert r["available"] is True
    assert 0 <= r["score"] <= 100
    txt = " ".join(r["suggestions"]).lower()
    assert "placement" in txt and "scholarship" in txt
    # things present must NOT be suggested
    assert "fees aren't visible" not in txt
    assert "no apply/enquire button" not in txt
    # mobile note appended when mobile-heavy
    assert any("mobile" in s.lower() for s in r["suggestions"])


# --------------------------- season pacing -------------------------------- #
def test_season_weights_pin_may_june_july_and_sum_to_one():
    w = _season_weights({})  # no data → even spread of the remaining 30%
    assert w[5] == 0.20 and w[6] == 0.30 and w[7] == 0.20
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_pacing_uses_admission_season():
    plan = build_plan(
        budget=1_500_000, timeframe_months=12, goal="traffic", assumed_cvr=0.0013,
        keyword_groups=[{"name": "Brand Intent", "intent": "brand",
                         "recommended_match_types": ["EXACT"]}],
        keyword_insights=[{"keyword": "x", "intent": "brand", "recommended_bid": 40}],
        seasonality={"available": False, "monthly_weights": {}, "months": []},
    )
    pacing = {p["month"]: p["budget"] for p in plan["monthly_pacing"]}
    assert pacing[6] == round(1_500_000 * 0.30)
    assert pacing[5] == round(1_500_000 * 0.20)
    assert pacing[7] == round(1_500_000 * 0.20)
    assert sum(pacing.values()) == 1_500_000  # exact


def test_landing_page_type_detection():
    from app.services.ai.landing_quality import detect_page_type, score_landing_page

    exam = {"fetched": True, "url": "http://lp.kollegeapply.com/NMAT2026/",
            "h1": ["NMAT 2026 Registration Open"], "cta_buttons": ["Register Now"],
            "admission_dates": ["Exam on 5 Dec"], "eligibility": ["Graduation required"],
            "h2": ["Exam Pattern", "Participating Colleges"], "meta_title": "NMAT",
            "meta_description": "Register for NMAT 2026"}
    assert detect_page_type(exam) == "exam"
    q = score_landing_page(exam, mobile_heavy=False)
    assert q["page_type"] == "exam"
    labels = [c["item"] for c in q["checks"]]
    assert any("Exam" in x or "Eligibility" in x for x in labels)
    assert not any("Placement" in x or "Scholarship" in x for x in labels)

    college = {"fetched": True, "url": "https://indusuni.ac.in/admissions",
               "h2": ["Placements", "Fee Structure", "Accreditation"], "h1": ["Admissions 2026"]}
    assert detect_page_type(college) == "college"
