"""Tests for the approval workflow + editable final strategy."""

from __future__ import annotations

from app.repositories.ad_copy import AdCopyRepository
from app.services.ai.approval_service import ApprovalService


def _make_gen(db):
    repo = AdCopyRepository(db)
    gen = repo.record({
        "campus": "Test College",
        "scores": {
            "campaign_plan": {
                "forecast": {"budget": 1_000_000, "est_clicks": 20_000},
                "bidding": {"recommended": "Maximize Clicks"},
            }
        },
    })
    db.commit()
    return gen


def test_approval_lifecycle_and_recompute(db_session):
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)

    assert svc.state(gen.id)["status"] == "draft"
    assert svc.state(gen.id)["cleared_to_launch"] is False

    svc.submit(gen.id, actor="operator")
    assert svc.state(gen.id)["status"] == "submitted"

    # Editing a value recomputes leads and resets approval to draft.
    st = svc.set_override(gen.id, field="target_cvr_pct", value=15.0, by="operator")
    assert st["status"] == "draft"
    assert st["final_strategy"]["est_leads"] == 3000  # 20,000 clicks * 15%
    assert st["final_strategy"]["est_cpl"] == round(1_000_000 / 3000)

    # Approve -> cleared to launch, with reviewer recorded.
    st = svc.decide(gen.id, approved=True, reviewer_name="Founder", note="ok")
    assert st["status"] == "approved"
    assert st["cleared_to_launch"] is True
    assert st["reviewer_name"] == "Founder"
    # events are newest-first
    assert [e["event"] for e in st["events"]][:3] == ["approved", "edited", "submitted"]


def test_non_editable_field_rejected(db_session):
    gen = _make_gen(db_session)
    r = ApprovalService(db_session).set_override(gen.id, field="nope", value=1, by="x")
    assert r["ok"] is False


def test_reject_sets_status(db_session):
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)
    st = svc.decide(gen.id, approved=False, reviewer_name="Reviewer", note="fix CVR target")
    assert st["status"] == "rejected"
    assert st["cleared_to_launch"] is False


def test_send_approval_without_smtp(db_session):
    gen = _make_gen(db_session)
    r = ApprovalService(db_session).send_approval(gen.id, to="x@y.com", actor="op")
    assert r["sent"] is False and r["configured"] is False
