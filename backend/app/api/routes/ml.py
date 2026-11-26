from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AnomalyServiceDep, get_current_user
from app.schemas import AnomalyOut, MlStatus

router = APIRouter(prefix="/ml", tags=["anomalias"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=MlStatus)
def status(service: AnomalyServiceDep) -> MlStatus:
    return service.status()


@router.get("/anomalies", response_model=list[AnomalyOut])
def anomalies(
    service: AnomalyServiceDep,
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
    target_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AnomalyOut]:
    return [
        AnomalyOut.model_validate(a)
        for a in service.recent(hours=hours, limit=limit, target_id=target_id)
    ]
