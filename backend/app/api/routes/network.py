from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import AdminUser, NetworkServiceDep, get_current_user
from app.core.logging import audit
from app.schemas import EventOut, NetworkStatus, TargetCreate, TargetOut, TargetUpdate

router = APIRouter(prefix="/network", tags=["network"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=NetworkStatus)
def network_status(service: NetworkServiceDep) -> NetworkStatus:
    return service.status()


@router.get("/targets", response_model=list[TargetOut])
def list_targets(service: NetworkServiceDep) -> list[TargetOut]:
    return [TargetOut.model_validate(t) for t in service.list_targets()]


@router.post("/targets", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def create_target(body: TargetCreate, service: NetworkServiceDep, admin: AdminUser) -> TargetOut:
    target = service.create_target(body)
    audit("target_created", actor=admin.username, host=target.host, name=target.name)
    return TargetOut.model_validate(target)


@router.patch("/targets/{target_id}", response_model=TargetOut)
def update_target(
    target_id: int, body: TargetUpdate, service: NetworkServiceDep, admin: AdminUser
) -> TargetOut:
    target = service.update_target(target_id, body)
    audit("target_updated", actor=admin.username, target_id=target_id)
    return TargetOut.model_validate(target)


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(target_id: int, service: NetworkServiceDep, admin: AdminUser) -> Response:
    service.delete_target(target_id)
    audit("target_deleted", actor=admin.username, target_id=target_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events", response_model=list[EventOut])
def list_events(
    service: NetworkServiceDep,
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
    active_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EventOut]:
    return [
        EventOut.model_validate(e)
        for e in service.list_events(hours=hours, active_only=active_only, limit=limit)
    ]
