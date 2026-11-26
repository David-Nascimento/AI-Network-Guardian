from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import MetricsServiceDep, get_current_user
from app.schemas import MetricPoint, MetricsComparison, MetricsSummary

router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(get_current_user)])

Hours = Annotated[int, Query(ge=1, le=24 * 90)]
TargetId = Annotated[int | None, Query(ge=1)]


@router.get("/history", response_model=list[MetricPoint])
def history(
    service: MetricsServiceDep,
    hours: Hours = 24,
    target_id: TargetId = None,
    bucket_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
) -> list[MetricPoint]:
    return service.history(hours=hours, target_id=target_id, bucket_minutes=bucket_minutes)


@router.get("/summary", response_model=MetricsSummary)
def summary(
    service: MetricsServiceDep, hours: Hours = 24, target_id: TargetId = None
) -> MetricsSummary:
    return service.summary(hours=hours, target_id=target_id)


@router.get("/compare", response_model=MetricsComparison)
def compare(
    service: MetricsServiceDep, hours: Hours = 24, target_id: TargetId = None
) -> MetricsComparison:
    return service.compare(hours=hours, target_id=target_id)
