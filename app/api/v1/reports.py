"""Module 10 - Reporting endpoints (JSON / CSV / Excel)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import get_reporting_service
from app.schemas.ops import ReportResponse
from app.services.ops.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["command-center"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/{period}",
    summary="Daily / weekly / monthly summary report",
    response_model=None,
)
def report(
    period: Literal["daily", "weekly", "monthly"],
    fmt: Literal["json", "csv", "excel"] = Query("json", alias="format"),
    account_id: int | None = Query(None),
    svc: ReportingService = Depends(get_reporting_service),
) -> Response:
    data = svc.build_report(period=period, account_id=account_id)
    stem = f"{period}_report_{data['end_date']}"

    if fmt == "csv":
        return StreamingResponse(
            iter([svc.render_csv(data)]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
        )
    if fmt == "excel":
        return StreamingResponse(
            iter([svc.render_excel(data)]),
            media_type=_XLSX,
            headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
        )
    # JSON (validated through the response schema).
    return Response(
        content=ReportResponse(**data).model_dump_json(),
        media_type="application/json",
    )
