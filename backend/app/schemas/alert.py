from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field

Severity = Literal["info", "warning", "critical"]
AlertStatus = Literal["new", "acknowledged", "resolved"]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    severity: Severity
    title: str
    message: str
    device_id: int | None
    created_at: datetime
    resolved_at: datetime | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> AlertStatus:
        if self.resolved_at is not None:
            return "resolved"
        return "acknowledged" if self.acknowledged_at is not None else "new"


class AlertSummary(BaseModel):
    new: int
    acknowledged: int
    critical_active: int


class AlertRuleOut(BaseModel):
    kind: str
    label: str
    description: str
    enabled: bool


class AlertRuleUpdate(BaseModel):
    enabled: bool
