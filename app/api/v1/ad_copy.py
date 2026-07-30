"""AI Ad Copy Generator endpoints (Phase 3 — AI Tools)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import get_ad_copy_service, require_api_key
from app.schemas.ad_copy import (
    AdCopyGenerateRequest,
    AdCopyGenerateResponse,
    AdCopyHistoryResponse,
    CampusSearchResponse,
    FinalUrlResponse,
)
from app.services.ai import ad_copy_export
from app.services.ai.ad_copy_service import AdCopyService

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
