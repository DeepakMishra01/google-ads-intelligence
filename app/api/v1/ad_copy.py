"""AI Ad Copy Generator endpoints (Phase 3 — AI Tools)."""

from __future__ import annotations

from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    get_ad_copy_service,
    get_current_user,
    require_admin,
    require_api_key,
)
from app.database.session import get_db
from app.schemas.ad_copy import (
    AdCopyGenerateRequest,
    AdCopyGenerateResponse,
    AdCopyHistoryResponse,
    CampusSearchResponse,
    FinalUrlResponse,
)
from app.services.ai import ad_copy_export
from app.services.ai.ad_copy_service import AdCopyService
from app.services.ai.approval_service import ApprovalService

router = APIRouter(prefix="/ai/ad-copy", tags=["ai-tools"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/campus/search", response_model=CampusSearchResponse, summary="Autocomplete campuses")
def campus_search(
    q: str | None = Query(None, description="Campus name / alias fragment."),
    limit: int = Query(10, ge=1, le=25),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> CampusSearchResponse:
    return CampusSearchResponse(**svc.search_campus(q, limit=limit))


@router.get(
    "/campus/final-url", response_model=FinalUrlResponse, summary="Discover the best Final URL"
)
def campus_final_url(
    campus: str = Query(..., description="Campus name."),
    override: str | None = Query(None, description="Manual Final-URL override."),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> FinalUrlResponse:
    return FinalUrlResponse(**svc.discover_url(campus, override=override))


@router.post(
    "/generate",
    response_model=AdCopyGenerateResponse,
    summary="Generate production-ready RSAs for a campus",
    dependencies=[Depends(require_api_key)],
)
def generate(
    body: AdCopyGenerateRequest,
    x_actor: str | None = Header(default=None, alias="X-Actor"),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> AdCopyGenerateResponse:
    result = svc.generate(
        campus=body.campus,
        account_id=body.account_id,
        final_url=body.final_url,
        tone=body.tone,
        persist=body.persist,
        actor=x_actor,
        budget=body.budget,
        goal=body.goal,
        timeframe_months=body.timeframe_months,
        assumed_cvr=body.assumed_cvr,
        target_cpl_low=body.target_cpl_low,
        target_cpl_high=body.target_cpl_high,
        target_leads=body.target_leads,
        conversion_tracking=body.conversion_tracking,
        lp_type=body.lp_type,
        manual_cpc=body.manual_cpc,
    )
    return AdCopyGenerateResponse(**result)


@router.get("/scorecard", response_model=None, summary="Objective vs expected vs achieved")
def scorecard(
    campus: str = Query(..., description="Campus name."),
    account_id: int | None = Query(None),
    target_leads: int = Query(2000, ge=1, description="Reference lead target for the objective."),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> dict:
    return svc.scorecard(campus=campus, account_id=account_id, target_leads=target_leads)


@router.post("/scorecard/save", response_model=None, summary="Save this week's scorecard")
def scorecard_save(
    campus: str = Query(...),
    account_id: int | None = Query(None),
    target_leads: int = Query(2000, ge=1),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> dict:
    return svc.save_scorecard(campus=campus, account_id=account_id, target_leads=target_leads)


@router.get("/scorecard/history", response_model=None, summary="Saved scorecard snapshots")
def scorecard_history(
    campus: str = Query(...),
    limit: int = Query(12, ge=1, le=52),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> dict:
    return svc.scorecard_history(campus=campus, limit=limit)


@router.get("/{gen_id}/approval", response_model=None, summary="Approval state + final strategy")
def approval_state(
    gen_id: int,
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).state(gen_id)


def _request_base_url(request: Request) -> str:
    """External base URL of THIS server, honoring a reverse proxy (Render, etc.).

    The approve/reject link must point back at the host that holds the plan, so we
    build it from the live request rather than a hard-coded default.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host.split(',')[0].strip()}"


@router.post("/{gen_id}/submit", response_model=None, summary="Submit strategy for review")
def approval_submit(
    gen_id: int,
    request: Request,
    x_actor: str | None = Header(None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).submit(
        gen_id, actor=x_actor, base_url=_request_base_url(request),
        submitter_user_id=user.id or None,  # 0 => synthetic admin (auth off)
    )


@router.get("/portfolio", response_model=None, summary="Campaign + ad-manager accountability")
def portfolio(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ai.portfolio_service import build_portfolio

    return build_portfolio(db, allowed_account_ids=user.allowed_account_ids)


@router.get("/account-budgets", response_model=None, summary="Account budgets: allotted vs spent")
def account_budgets(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ai.portfolio_service import build_portfolio

    p = build_portfolio(db, allowed_account_ids=user.allowed_account_ids)
    return {
        "accounts": p["accounts"],
        "alerts": p["account_alerts"],
        "as_of": p["as_of"],
    }


@router.post("/landing-audit", response_model=None, summary="Audit any landing-page URL")
def landing_audit(
    url: str = Query(..., description="Landing page URL to audit."),
    lp_type: str = Query("auto", description="auto | kapp | client — landing-page ownership."),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ai.landing_auditor import build_landing_audit
    from app.services.ai.landing_page_service import LandingPageService
    from app.services.ai.landing_quality import score_landing_page

    landing = LandingPageService(db).analyze(url)
    if not landing.get("fetched"):
        return {
            "fetched": False,
            "url": url,
            "notes": landing.get("notes", "The page could not be fetched."),
        }
    quality = score_landing_page(landing)
    audit = build_landing_audit(landing, quality, lp_type=lp_type)
    return {
        "fetched": True,
        "url": landing.get("url", url),
        "landing": landing,
        "landing_quality": quality,
        "landing_audit": audit,
    }


@router.get("/execution-audit", response_model=None, summary="Plan-vs-reality per ad manager")
def execution_audit(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.ai.execution_audit_service import build_manager_audit

    return build_manager_audit(db, allowed_account_ids=user.allowed_account_ids)


@router.get("/execution-audit/{gen_id}", response_model=None, summary="Given-vs-used detail")
def execution_audit_detail(gen_id: int, db: Session = Depends(get_db)) -> dict:
    from app.repositories.ad_copy import AdCopyRepository
    from app.services.ai.execution_audit_service import build_campaign_audit

    return build_campaign_audit(db, AdCopyRepository(db).get(gen_id))


@router.post("/{gen_id}/request-changes", response_model=None, summary="Ask for changes")
def approval_request_changes(
    gen_id: int,
    reviewer_name: str = Query(...),
    note: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).request_changes(
        gen_id, reviewer_name=reviewer_name, note=note
    )


@router.post("/{gen_id}/ad-manager", response_model=None, summary="Assign the ad manager")
def approval_set_ad_manager(
    gen_id: int,
    name: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).set_ad_manager(gen_id, name=name)


@router.post("/{gen_id}/owner", response_model=None, summary="Assign the owning user (access)")
def approval_set_owner(
    gen_id: int,
    user_id: int | None = Query(None, description="User id to own this campaign; omit to clear."),
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).set_owner(gen_id, user_id=user_id)


@router.post("/{gen_id}/account", response_model=None, summary="Assign the target ad account")
def approval_set_account(
    gen_id: int,
    customer_id: str = Query(..., description="Google Ads customer ID to build the campaign in."),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).set_account(gen_id, customer_id=customer_id)


@router.post("/{gen_id}/decide", response_model=None, summary="Approve or reject a strategy")
def approval_decide(
    gen_id: int,
    approved: bool = Query(...),
    reviewer_name: str = Query(..., min_length=1),
    note: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).decide(
        gen_id, approved=approved, reviewer_name=reviewer_name, note=note
    )


@router.post("/{gen_id}/override", response_model=None, summary="Edit a final-strategy value")
def approval_override(
    gen_id: int,
    field: str = Query(...),
    value: str = Query(...),
    by: str | None = Header(None, alias="X-Actor"),
    db: Session = Depends(get_db),
) -> dict:
    # numeric fields come in as strings from the query; coerce where sensible.
    v: object = value
    if field in ("budget", "target_leads", "target_cvr_pct"):
        try:
            v = float(value)
            if field in ("target_leads",):
                v = int(v)
        except ValueError:
            v = value
    return ApprovalService(db).set_override(gen_id, field=field, value=v, by=by)


@router.post("/{gen_id}/send-approval", response_model=None, summary="Email strategy for approval")
def approval_email(
    gen_id: int,
    request: Request,
    to: str | None = Query(None, description="Override recipient; default = platform admins."),
    x_actor: str | None = Header(None, alias="X-Actor"),
    db: Session = Depends(get_db),
) -> dict:
    svc = ApprovalService(db)
    recipients = to or svc._approver_recipients()
    if not recipients:
        return {"sent": False, "reason": "No admin recipients configured."}
    return svc.send_approval(
        gen_id, to=recipients, actor=x_actor, base_url=_request_base_url(request)
    )


def _decision_page(title: str, message: str, ok: bool) -> HTMLResponse:
    color = "#16a34a" if ok else "#dc2626"
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:48px 16px">
  <div style="max-width:440px;margin:0 auto;background:#fff;border-radius:12px;
       box-shadow:0 1px 3px rgba(0,0,0,.1);padding:32px;text-align:center">
    <div style="font-size:44px;line-height:1;color:{color}">{'✓' if ok else '✗'}</div>
    <h1 style="margin:12px 0 6px;font-size:20px;color:#0f172a">{title}</h1>
    <p style="color:#475569;font-size:14px">{message}</p>
  </div>
</body></html>"""
    return HTMLResponse(content=html, status_code=200 if ok else 400)


@router.get("/{gen_id}/approve", response_model=None, summary="One-click approve (email link)")
def approval_approve_link(
    gen_id: int, token: str = Query(...), db: Session = Depends(get_db)
) -> HTMLResponse:
    r = ApprovalService(db).approve_via_token(gen_id, token=token, reject=False)
    if not r.get("ok"):
        return _decision_page("Link not valid", str(r.get("reason", "")), ok=False)
    return _decision_page(
        "Approved — cleared to launch",
        f"“{r.get('campus', 'This plan')}” is approved and the submitter has been "
        "emailed that they can build the campaign in Google Ads. You can close this tab.",
        ok=True,
    )


def _reject_form_page(gen_id: int, token: str, campus: str) -> HTMLResponse:
    """A page (opened from the email) where the reviewer types WHY they're rejecting."""
    action = f"/api/v1/ai/ad-copy/{gen_id}/reject/confirm"
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Request changes</title></head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;margin:0;padding:48px 16px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;
       box-shadow:0 1px 3px rgba(0,0,0,.1);padding:28px">
    <h1 style="margin:0 0 4px;font-size:20px;color:#0f172a">Request changes</h1>
    <p style="color:#475569;font-size:14px;margin:0 0 16px">
      Tell the submitter what to change on “<b>{escape(campus)}</b>”. Your comments are
      emailed to them so they can revise and resubmit.</p>
    <form method="get" action="{action}">
      <input type="hidden" name="token" value="{escape(token)}">
      <textarea name="note" rows="5" required placeholder="e.g. Budget too high for this campus; tighten brand keywords; fix the landing page form…"
        style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;
        padding:12px;font-size:14px;font-family:inherit;resize:vertical"></textarea>
      <button type="submit" style="margin-top:14px;background:#d97706;color:#fff;border:0;
        border-radius:8px;padding:11px 18px;font-size:14px;font-weight:bold;cursor:pointer">
        Send back with these comments</button>
    </form>
  </div>
</body></html>"""
    return HTMLResponse(content=html, status_code=200)


@router.get("/{gen_id}/reject", response_model=None, summary="Reject → comment form (email link)")
def approval_reject_link(
    gen_id: int, token: str = Query(...), db: Session = Depends(get_db)
) -> HTMLResponse:
    # Validate the token, then show a comment box (don't reject until they submit it).
    from app.models.ad_copy import AdCopyGeneration

    gen = db.get(AdCopyGeneration, gen_id)
    if gen is None or not gen.approval_token or gen.approval_token != token:
        return _decision_page("Link not valid", "Invalid or expired link.", ok=False)
    return _reject_form_page(gen_id, token, gen.campus)


@router.get("/{gen_id}/reject/confirm", response_model=None, summary="Confirm reject with comments")
def approval_reject_confirm(
    gen_id: int,
    token: str = Query(...),
    note: str = Query("", description="Reviewer's reason for the changes."),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    r = ApprovalService(db).approve_via_token(gen_id, token=token, reject=True, note=note)
    if not r.get("ok"):
        return _decision_page("Link not valid", str(r.get("reason", "")), ok=False)
    return _decision_page(
        "Changes requested",
        f"Your comments on “{r.get('campus', 'this plan')}” were sent to the submitter so "
        "they can revise and resubmit. You can close this tab.",
        ok=False,
    )


@router.get("/history", response_model=AdCopyHistoryResponse, summary="Recent generations")
def history(
    campus: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> AdCopyHistoryResponse:
    return AdCopyHistoryResponse(**svc.history_rows(campus=campus, limit=limit))


@router.get("/{gen_id}/export", response_model=None, summary="Export a generation (excel/csv/json)")
def export(
    gen_id: int,
    fmt: Literal["excel", "csv", "json"] = Query("excel", alias="format"),
    user: CurrentUser = Depends(get_current_user),
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> Response:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Downloads are admin-only.")
    gen = svc.get_generation(gen_id)
    if gen is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    stem = f"adcopy_{gen.campus.replace(' ', '_')}_{gen_id}"

    if fmt == "csv":
        return StreamingResponse(
            iter([ad_copy_export.render_csv(gen)]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
        )
    if fmt == "excel":
        return StreamingResponse(
            iter([ad_copy_export.render_excel(gen)]),
            media_type=_XLSX,
            headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
        )
    return Response(content=ad_copy_export.render_json(gen), media_type="application/json")
