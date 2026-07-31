"""AI Ad Copy Generator endpoints (Phase 3 — AI Tools)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_ad_copy_service, require_api_key
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
        conversion_tracking=body.conversion_tracking,
        lp_type=body.lp_type,
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


@router.post("/{gen_id}/submit", response_model=None, summary="Submit strategy for review")
def approval_submit(
    gen_id: int,
    x_actor: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).submit(gen_id, actor=x_actor)


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
    to: str = Query(..., description="Reviewer email address."),
    x_actor: str | None = Header(None, alias="X-Actor"),
    db: Session = Depends(get_db),
) -> dict:
    return ApprovalService(db).send_approval(gen_id, to=to, actor=x_actor)


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
    svc: AdCopyService = Depends(get_ad_copy_service),
) -> Response:
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
