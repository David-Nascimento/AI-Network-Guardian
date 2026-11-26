from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AdminUser, AlertServiceDep, get_current_user
from app.core.logging import audit
from app.repositories.alerts import StatusFilter
from app.schemas import AlertOut, AlertRuleOut, AlertRuleUpdate, AlertSummary, BulkResult

router = APIRouter(prefix="/alerts", tags=["alertas"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    service: AlertServiceDep,
    status: StatusFilter = "active",
    severity: Annotated[str | None, Query(pattern="^(info|warning|critical)$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AlertOut]:
    return [
        AlertOut.model_validate(a)
        for a in service.list(status=status, severity=severity, limit=limit)
    ]


@router.get("/summary", response_model=AlertSummary)
def summary(service: AlertServiceDep) -> AlertSummary:
    return service.summary()


@router.get("/rules", response_model=list[AlertRuleOut])
def rules(service: AlertServiceDep) -> list[AlertRuleOut]:
    return service.rules()


@router.patch("/rules/{kind}", response_model=AlertRuleOut)
def update_rule(
    kind: str, body: AlertRuleUpdate, service: AlertServiceDep, admin: AdminUser
) -> AlertRuleOut:
    rule = service.set_rule(kind, body.enabled)
    audit("alert_rule_changed", actor=admin.username, kind=kind, enabled=body.enabled)
    return rule


@router.post("/ack-all", response_model=BulkResult)
def acknowledge_all(service: AlertServiceDep, admin: AdminUser) -> BulkResult:
    updated = service.acknowledge_all(admin.username)
    audit("alerts_acknowledged_all", actor=admin.username, updated=updated)
    return BulkResult(updated=updated)


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge(alert_id: int, service: AlertServiceDep, admin: AdminUser) -> AlertOut:
    alert = service.acknowledge(alert_id, admin.username)
    audit("alert_acknowledged", actor=admin.username, alert_id=alert_id)
    return AlertOut.model_validate(alert)
