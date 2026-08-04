"""Tests for the Execution Audit (plan vs live, per ad manager)."""

from __future__ import annotations

from app.services.ai.execution_audit_service import _copy_used, _norm_kw


def test_norm_kw_strips_match_punctuation():
    assert _norm_kw('[Indus University]') == "indus university"
    assert _norm_kw('"indus  admission"') == "indus admission"
    assert _norm_kw("  MBA Fees ") == "mba fees"


def test_copy_used_exact_and_fuzzy():
    live = {"mica admissions 2026 open", "apply now for mica pgdm"}
    # exact (after normalisation)
    assert _copy_used("MICA Admissions 2026 Open", live) is True
    # fuzzy: recommended line contained in a live (lightly-edited) line
    assert _copy_used("apply now", live) is True
    # not present at all
    assert _copy_used("Scholarships available", live) is False


def test_manager_audit_only_assigned(db_session):
    from app.repositories.ad_copy import AdCopyRepository
    from app.services.ai.execution_audit_service import build_manager_audit

    repo = AdCopyRepository(db_session)
    # one assigned, one not
    repo.record({"campus": "Alpha", "ad_manager": "A. Sharma",
                 "generated_assets": {"headlines": [], "descriptions": []},
                 "keyword_snapshot": {"keywords": []}})
    repo.record({"campus": "Beta",
                 "generated_assets": {"headlines": [], "descriptions": []},
                 "keyword_snapshot": {"keywords": []}})
    db_session.commit()
    m = build_manager_audit(db_session)
    assert m["assigned_campaigns"] == 1
    assert [x["ad_manager"] for x in m["managers"]] == ["A. Sharma"]
