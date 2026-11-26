from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    window_start: datetime
    method: str
    score: float
    features: dict[str, float]
    deviations: list[str]


class MlTargetStatus(BaseModel):
    target_id: int
    name: str
    windows: int
    ready: bool


class MlStatus(BaseModel):
    enabled: bool
    configured_method: str
    effective_method: str | None  # None enquanto não há dados suficientes em nenhum destino
    sklearn_available: bool
    window_minutes: int
    min_windows: int
    train_hours: int
    targets: list[MlTargetStatus]
