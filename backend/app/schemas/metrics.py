from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MetricPoint(BaseModel):
    ts: datetime
    target_id: int
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float
    samples: int


class MetricsSummary(BaseModel):
    since: datetime
    until: datetime
    samples: int
    availability_pct: float | None
    latency_min_ms: float | None
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_avg_ms: float | None
    packet_loss_avg_pct: float | None


class MetricsComparison(BaseModel):
    current: MetricsSummary
    previous: MetricsSummary
    latency_avg_delta_ms: float | None
    packet_loss_delta_pct: float | None
    availability_delta_pct: float | None
