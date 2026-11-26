from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TargetReport(BaseModel):
    target_id: int
    name: str
    availability_pct: float | None
    latency_avg_ms: float | None
    packet_loss_avg_pct: float | None
    samples: int


class IncidentReport(BaseModel):
    count: int
    downtime_seconds: int
    by_type: dict[str, int]


class DeviceReport(BaseModel):
    total: int
    online: int
    known: int
    unknown: int
    first_seen_in_period: int


class AlertReport(BaseModel):
    created: int
    by_kind: dict[str, int]
    still_active: int


class ReportSummary(BaseModel):
    generated_at: datetime
    since: datetime
    until: datetime
    hours: int
    availability_pct: float | None
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_avg_ms: float | None
    packet_loss_avg_pct: float | None
    samples: int
    targets: list[TargetReport]
    incidents: IncidentReport
    devices: DeviceReport
    alerts: AlertReport
    anomalies: int
    notes: list[str]
