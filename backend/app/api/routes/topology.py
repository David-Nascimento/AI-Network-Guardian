from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import TopologyServiceDep, get_current_user
from app.schemas import Topology

router = APIRouter(prefix="/topology", tags=["topology"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=Topology)
def topology(service: TopologyServiceDep) -> Topology:
    return service.build()
