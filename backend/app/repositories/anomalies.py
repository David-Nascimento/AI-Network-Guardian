from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Anomaly


class AnomalyRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def exists(self, target_id: int, window_start: datetime) -> bool:
        return (
            self._s.scalars(
                select(Anomaly.id).where(
                    Anomaly.target_id == target_id, Anomaly.window_start == window_start
                )
            ).first()
            is not None
        )

    def add(self, anomaly: Anomaly) -> Anomaly:
        self._s.add(anomaly)
        self._s.flush()
        return anomaly

    def recent(self, since: datetime, limit: int, target_id: int | None = None) -> list[Anomaly]:
        stmt = select(Anomaly).where(Anomaly.window_start >= since)
        if target_id is not None:
            stmt = stmt.where(Anomaly.target_id == target_id)
        return list(self._s.scalars(stmt.order_by(Anomaly.window_start.desc()).limit(limit)))
