from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

TargetKind = Literal["gateway", "external", "dns"]
TargetMethod = Literal["icmp", "tcp", "dns"]
ConnectivityState = Literal["online", "degraded", "offline", "unknown"]


class _TargetRules(BaseModel):
    """Regras de coerência entre tipo, método e porta na criação de um destino."""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        method = getattr(self, "method", None)
        port = getattr(self, "port", None)
        kind = getattr(self, "kind", None)
        if method == "tcp" and port is None:
            raise ValueError("método tcp exige 'port'")
        if method != "tcp" and port is not None:
            raise ValueError("'port' só se aplica ao método tcp")
        if (kind == "dns") != (method == "dns"):
            raise ValueError("kind 'dns' e method 'dns' devem andar juntos")
        return self


class TargetCreate(_TargetRules):
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253)
    kind: TargetKind
    method: TargetMethod
    port: int | None = Field(default=None, ge=1, le=65535)
    enabled: bool = True


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    kind: TargetKind
    method: TargetMethod
    port: int | None
    enabled: bool
    created_at: datetime


class TargetStatus(BaseModel):
    target: TargetOut
    down: bool
    last_sample_at: datetime | None
    latency_avg_ms: float | None
    packet_loss_pct: float | None


class NetworkStatus(BaseModel):
    state: ConnectivityState
    summary: str
    checked_at: datetime
    targets: list[TargetStatus]
    active_events: list[EventOut]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    severity: str
    target_id: int | None
    message: str
    details: dict[str, object]
    started_at: datetime
    ended_at: datetime | None


NetworkStatus.model_rebuild()
