from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import CurrentUser, ReportServiceDep, get_current_user
from app.core.logging import audit
from app.schemas import ReportSummary
from app.services.report_service import ExportKind

router = APIRouter(prefix="/reports", tags=["relatórios"], dependencies=[Depends(get_current_user)])

Hours = Annotated[int, Query(ge=1, le=720)]


@router.get("/summary", response_model=ReportSummary)
def summary(service: ReportServiceDep, hours: Hours = 24) -> ReportSummary:
    return service.summary(hours)


@router.get("/export")
def export(
    service: ReportServiceDep, user: CurrentUser, kind: ExportKind, hours: Hours = 24
) -> Response:
    filename, content = service.export(kind, hours)
    audit("report_exported", actor=user.username, kind=kind, hours=hours)
    return Response(
        content="﻿" + content,  # BOM: o Excel abre com acentos corretos
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
