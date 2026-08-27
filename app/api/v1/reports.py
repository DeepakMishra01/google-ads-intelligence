"""Module 10 - Reporting endpoints (JSON / CSV / Excel)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    CurrentUser,
    _assert_account_allowed,
    get_current_user,
    get_reporting_service,
)
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
    user: CurrentUser = Depends(get_current_user),
    svc: ReportingService = Depends(get_reporting_service),
) -> Response:
    # Managers may download a report for an account they own; only admins can pull
    # the all-accounts (account_id=None) file. This keeps cross-account data from
    # leaking while letting managers export their own account's report.
    if not user.is_admin and user.allowed_account_ids is not None:
        if account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select one of your assigned accounts to download its report.",
            )
        _assert_account_allowed(account_id, user)
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
