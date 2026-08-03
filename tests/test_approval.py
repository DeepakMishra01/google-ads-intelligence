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


def test_submit_generates_token_and_attempts_email(db_session):
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)
    st = svc.submit(gen.id, actor="Deepak")
    assert st["status"] == "submitted"
    # A per-plan token is minted so the email links work.
    assert gen.approval_token
    # Auto-send is attempted to the fixed reviewer inbox (no SMTP in tests -> not sent).
    assert st["email"] is not None
    assert st["email"]["sent"] is False


def test_one_click_approve_via_token(db_session):
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)
    svc.submit(gen.id, actor="Deepak")
    token = gen.approval_token

    # Wrong token is rejected.
    bad = svc.approve_via_token(gen.id, token="nope", reject=False)
    assert bad["ok"] is False

    # Correct token approves and clears to launch, recording the reviewer.
    ok = svc.approve_via_token(gen.id, token=token, reject=False)
    assert ok["ok"] is True
    assert ok["status"] == "approved"
    assert ok["cleared_to_launch"] is True
    assert ok["reviewer_name"]  # the fixed reviewer inbox


def test_decision_urls_point_at_submit_host(db_session):
    # The link must resolve to the host the plan was submitted on (its own DB),
    # not a hard-coded default — this is the cross-environment bug fix.
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)
    approve, reject = svc._decision_urls(gen, "http://localhost:8000")
    assert approve.startswith("http://localhost:8000/api/v1/ai/ad-copy/")
    assert "/approve?token=" in approve
    assert "/reject?token=" in reject


def test_one_click_reject_via_token(db_session):
    gen = _make_gen(db_session)
    svc = ApprovalService(db_session)
    svc.submit(gen.id, actor="Deepak")
    r = svc.approve_via_token(gen.id, token=gen.approval_token, reject=True)
    assert r["ok"] is True
    assert r["status"] == "rejected"
    assert r["cleared_to_launch"] is False
