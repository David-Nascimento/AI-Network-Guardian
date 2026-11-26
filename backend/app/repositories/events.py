from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NetworkEvent


class EventRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, event: NetworkEvent) -> NetworkEvent:
        self._s.add(event)
        self._s.flush()
        return event

    def open_events(self) -> list[NetworkEvent]:
        return list(self._s.scalars(select(NetworkEvent).where(NetworkEvent.ended_at.is_(None))))

    def list(self, *, since: datetime, active_only: bool, limit: int) -> list[NetworkEvent]:
        stmt = (
            select(NetworkEvent)
            .where(NetworkEvent.started_at >= since)
            .order_by(NetworkEvent.started_at.desc())
            .limit(limit)
        )
        if active_only:
            stmt = stmt.where(NetworkEvent.ended_at.is_(None))
        return list(self._s.scalars(stmt))
