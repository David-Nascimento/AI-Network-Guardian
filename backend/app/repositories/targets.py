from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MonitorTarget


class TargetRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, target_id: int) -> MonitorTarget | None:
        return self._s.get(MonitorTarget, target_id)

    def get_by_name(self, name: str) -> MonitorTarget | None:
        return self._s.scalar(select(MonitorTarget).where(MonitorTarget.name == name))

    def list(self, *, enabled_only: bool = False) -> list[MonitorTarget]:
        stmt = select(MonitorTarget).order_by(MonitorTarget.id)
        if enabled_only:
            stmt = stmt.where(MonitorTarget.enabled.is_(True))
        return list(self._s.scalars(stmt))

    def count(self) -> int:
        return self._s.scalar(select(func.count(MonitorTarget.id))) or 0

    def add(self, target: MonitorTarget) -> MonitorTarget:
        self._s.add(target)
        self._s.flush()
        return target

    def delete(self, target: MonitorTarget) -> None:
        self._s.delete(target)
        self._s.flush()
