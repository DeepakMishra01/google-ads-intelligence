"""Tests for the AI Ad Copy Generator module (Phase 3).

Pure-logic tests (intent, scoring, validation, landing-page parsing) run without
a DB; the Final-URL ranking test seeds a minimal campus; API tests use the
TestClient with the deterministic backend (no LLM key) and a stubbed landing page
so nothing hits the network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.account import Account
from app.models.ad import Ad, AdSnapshot
from app.models.ad_group import AdGroup
from app.models.campaign import Campaign
from app.services.ai import intent_classifier, keyword_scorer, rsa_validator
from app.services.ai.campus_config import find_brief, generic_brief
from app.services.ai.campus_service import CampusService
from app.services.ai.landing_page_service import LandingPageService

SNAP = date.today() - timedelta(days=2)


# --------------------------- intent classification ------------------------- #
@pytest.mark.parametrize(
    "kw,expected",
    [
        ("mica last date to apply", "deadline"),
        ("indus university application form", "application"),
        ("micat registration 2026", "registration"),
        ("mica admission", "admission"),
        ("mba fees", "fees"),
        ("pgdm course", "course"),
    ],
)
def test_intent_classification(kw, expected):
    r = intent_classifier.classify(kw, brand_terms=["mica", "indus"])
    assert r["intent"] == expected
    assert 0 < r["confidence"] <= 1


def test_intent_high_vs_low_commercial():
    assert intent_classifier.classify("apply online mica")["commercial_intent"] == "high"
    assert intent_classifier.classify("mba placement package")["commercial_intent"] == "low"


# --------------------------- keyword scoring ------------------------------- #
def test_scorer_rewards_performance_and_intent():
    strong = keyword_scorer.score_keyword(
        {"commercial_intent": "high", "historical_ctr": 0.12, "historical_clicks": 300,
         "quality_score": 9, "historical_cpc": 15}
    )["score"]
    weak = keyword_scorer.score_keyword(
        {"commercial_intent": "low", "historical_ctr": 0.01, "historical_clicks": 2,
         "quality_score": 3, "historical_cpc": 120}
    )["score"]
    assert strong > weak
    assert 0 <= weak <= 100 and 0 <= strong <= 100


def test_scorer_handles_missing_signals():
    r = keyword_scorer.score_keyword({"keyword": "x"})
    assert r["score"] == 0.0  # no signals → neutral/zero, no crash


# --------------------------- RSA validation -------------------------------- #
def test_validator_flags_overlength_and_predicts_strength():
    too_long = "This headline is definitely way too long to allow at all"
    q = rsa_validator.validate_assets(
        headlines=["MICA", "Apply to MICA 2026", too_long],
        descriptions=["Apply to MICA now for 2026 admissions.", "MICA admissions are open today."],
    )
    assert any(f["level"] == "error" and f["field"] == "headline" for f in q["flags"])
    assert q["expected_ad_strength"] in {"POOR", "AVERAGE", "GOOD", "EXCELLENT"}


def test_validator_full_rsa_is_strong():
    heads = [f"MICA Headline {i}" for i in range(15)]
    descs = [f"MICA admissions description number {i} for 2026 intake." for i in range(4)]
    q = rsa_validator.validate_assets(
        headlines=heads, descriptions=descs, keyword_themes=["mica", "headline"]
    )
    assert q["headline_count"] == 15
    assert q["expected_ad_strength"] in {"GOOD", "EXCELLENT"}


# --------------------------- campus config --------------------------------- #
def test_find_brief_and_fallback():
    assert find_brief("MICA").short == "MICA"
    assert find_brief("indus university").short == "Indus"
    assert find_brief("totally unknown campus xyz") is None
    g = generic_brief("Brand New College")
    assert g.brand == "Brand New College" and g.programs


# --------------------------- landing page parser --------------------------- #
def test_landing_page_parser_extracts_facts():
    html = """
    <html><head><title>MICA Admissions 2026</title>
    <meta name="description" content="Apply to MICA PGDM-C programme."></head>
    <body><h1>MICA Ahmedabad</h1><h2>PGDM-C Programme</h2>
    <a href="/apply">Apply Now</a>
    <p>Last date to apply is 30 June 2026.</p>
    <p>Eligibility: graduation with 50%.</p>
    </body></html>
    """
    svc = LandingPageService(None)
    out = svc._parse("https://example.edu/admissions", html)
    assert out["fetched"] is True
    assert out["title"] == "MICA Admissions 2026"
    assert any("apply" in c.lower() for c in out["cta_buttons"])
    assert out["deadlines"], "should detect the 'last date' line"
    assert out["eligibility"], "should detect the eligibility line"


def test_landing_page_refuses_private_host():
    svc = LandingPageService(None)
    out = svc.analyze("http://localhost:8000/secret")
    assert out["fetched"] is False


# --------------------------- Final-URL discovery --------------------------- #
def _seed_mica(db):
    acc = Account(customer_id="9990001", descriptive_name="Kollege-MICA", is_syncable=True)
    db.add(acc)
    db.flush()
    camp = Campaign(account_id=acc.id, campaign_id=111, name="MICA Admissions 2026")
    db.add(camp)
    db.flush()
    ag = AdGroup(account_id=acc.id, campaign_id=camp.id, ad_group_id=222, name="Brand")
    db.add(ag)
    db.flush()
    # Two ads: a high-spend and a low-spend landing page.
    hi = Ad(account_id=acc.id, ad_group_id=ag.id, ad_id=1,
            final_urls="https://www.mica.ac.in/admissions2026/")
    lo = Ad(account_id=acc.id, ad_group_id=ag.id, ad_id=2,
            final_urls="https://www.mica.ac.in/contact/")
    db.add_all([hi, lo])
    db.flush()
    db.add(AdSnapshot(snapshot_date=SNAP, account_id=acc.id, ad_id=hi.id, ad_group_id=ag.id,
                      campaign_id=camp.id, cost_micros=90_000_000, clicks=200, impressions=4000))
    db.add(AdSnapshot(snapshot_date=SNAP, account_id=acc.id, ad_id=lo.id, ad_group_id=ag.id,
                      campaign_id=camp.id, cost_micros=5_000_000, clicks=10, impressions=500))
    db.commit()


def test_final_url_ranks_by_spend(db_session):
    _seed_mica(db_session)
    svc = CampusService(db_session)
    brief = find_brief("MICA")
    result = svc.discover_final_url(brief)
    assert result["selected"]["url"].startswith("https://www.mica.ac.in/admissions2026")
    assert result["selected"]["source"] == "historical_ads"
    assert result["selected"]["confidence"] > 0.5


def test_final_url_falls_back_to_homepage(db_session):
    # No history seeded → homepage fallback from the curated brief.
    svc = CampusService(db_session)
    brief = find_brief("XIME")
    result = svc.discover_final_url(brief)
    assert result["selected"] is not None
    assert result["selected"]["source"] == "homepage"


def test_manual_override_wins(db_session):
    svc = CampusService(db_session)
    brief = find_brief("MICA")
    result = svc.discover_final_url(brief, override="https://custom.example.edu/lp")
    assert result["selected"]["url"] == "https://custom.example.edu/lp"
    assert result["selected"]["source"] == "manual"


# --------------------------- API smoke ------------------------------------- #
@pytest.fixture
def _no_network_landing(monkeypatch):
    """Stub landing-page analysis so API tests never hit the network."""
    from app.services.ai.landing_page_service import LandingPageService

    monkeypatch.setattr(
        LandingPageService, "analyze",
        lambda self, url: {"url": url or "", "fetched": False, "notes": "stubbed in test"},
    )


def test_api_campus_search(client):
    r = client.get("/api/v1/ai/ad-copy/campus/search", params={"q": "mica"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["campus"] == "MICA" for i in items)


def test_api_generate_and_export(client, _no_network_landing):
    r = client.post("/api/v1/ai/ad-copy/generate", json={"campus": "MICA", "persist": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backend"] == "template"  # no LLM key in tests
    assert len(body["assets"]["headlines"]) == 15
    assert len(body["assets"]["descriptions"]) == 4
    assert all(h["length"] <= 30 for h in body["assets"]["headlines"])
    assert all(d["length"] <= 90 for d in body["assets"]["descriptions"])
    assert body["quality"]["expected_ad_strength"] in {"GOOD", "EXCELLENT"}
    gen_id = body["id"]
    assert gen_id

    # Export the persisted generation.
    ex = client.get(f"/api/v1/ai/ad-copy/{gen_id}/export", params={"format": "excel"})
    assert ex.status_code == 200
    assert ex.headers["content-type"].startswith("application/vnd.openxml")
    assert len(ex.content) > 1000

    csv = client.get(f"/api/v1/ai/ad-copy/{gen_id}/export", params={"format": "csv"})
    assert csv.status_code == 200
    assert "Headline" in csv.text


def test_api_export_404(client):
    r = client.get("/api/v1/ai/ad-copy/999999/export")
    assert r.status_code == 404
