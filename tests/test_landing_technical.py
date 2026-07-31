"""Tests for extended (technical) landing-page checks in the auditor."""

from __future__ import annotations

from app.services.ai.landing_auditor import build_landing_audit


def _landing(**over):
    base = {
        "fetched": True,
        "url": "https://kollegeapply.com/indus",
        "tracking": {"gtm": True, "google_ads_conversion": True, "ga4": True},
        "load_ms": 1200,
        "has_viewport": True,
        "has_form": True,
        "has_privacy": True,
        "has_terms": True,
        "h1": ["Indus University Admissions 2026 — Apply Now"],
    }
    base.update(over)
    return base


def _by_item(audit, item):
    return next(c for c in audit["technical_checks"] if c["item"] == item)


def test_technical_checks_all_pass():
    audit = build_landing_audit(
        _landing(), {"available": True, "score": 90}, brand="Indus University"
    )
    assert audit["available"] is True
    assert _by_item(audit, "Page load speed")["status"] == "pass"
    assert _by_item(audit, "Mobile viewport tag")["status"] == "pass"
    assert _by_item(audit, "Privacy policy link")["status"] == "pass"
    assert _by_item(audit, "H1 ↔ ad message match")["status"] == "pass"


def test_slow_page_fails_speed():
    audit = build_landing_audit(
        _landing(load_ms=7000), {"available": True, "score": 80}, brand="Indus"
    )
    assert _by_item(audit, "Page load speed")["status"] == "fail"


def test_missing_viewport_and_privacy_fail():
    audit = build_landing_audit(
        _landing(has_viewport=False, has_privacy=False),
        {"available": True, "score": 80},
        brand="Indus University",
    )
    assert _by_item(audit, "Mobile viewport tag")["status"] == "fail"
    assert _by_item(audit, "Privacy policy link")["status"] == "fail"


def test_h1_without_brand_warns():
    audit = build_landing_audit(
        _landing(h1=["Welcome to our website"]),
        {"available": True, "score": 80},
        brand="Indus University",
    )
    assert _by_item(audit, "H1 ↔ ad message match")["status"] == "warn"


def test_no_form_warns():
    audit = build_landing_audit(
        _landing(has_form=False), {"available": True, "score": 80}, brand="Indus"
    )
    assert _by_item(audit, "Lead-capture form")["status"] == "warn"
