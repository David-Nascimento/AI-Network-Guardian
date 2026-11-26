from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Alert, AlertRule

StatusFilter = Literal["active", "new", "acknowledged", "resolved", "all"]


class AlertRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, alert_id: int) -> Alert | None:
        return self._s.get(Alert, alert_id)

    def open_by_key(self, dedupe_key: str) -> Alert | None:
        return self._s.scalars(
            select(Alert).where(Alert.dedupe_key == dedupe_key, Alert.resolved_at.is_(None))
        ).first()

    def add(self, alert: Alert) -> Alert:
        self._s.add(alert)
        self._s.flush()
        return alert

    def find(self, *, status: StatusFilter, severity: str | None, limit: int) -> list[Alert]:
        stmt = select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
        if status == "active":
            stmt = stmt.where(Alert.resolved_at.is_(None))
        elif status == "new":
            stmt = stmt.where(Alert.resolved_at.is_(None), Alert.acknowledged_at.is_(None))
        elif status == "acknowledged":
            stmt = stmt.where(Alert.resolved_at.is_(None), Alert.acknowledged_at.is_not(None))
        elif status == "resolved":
            stmt = stmt.where(Alert.resolved_at.is_not(None))
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        return list(self._s.scalars(stmt))

    def count_active(self) -> tuple[int, int, int]:
        """(novos, reconhecidos, críticos ativos)."""
        active = Alert.resolved_at.is_(None)
        new = self._count(active, Alert.acknowledged_at.is_(None))
        acknowledged = self._count(active, Alert.acknowledged_at.is_not(None))
        critical = self._count(active, Alert.severity == "critical")
        return new, acknowledged, critical

    def _count(self, *conditions: object) -> int:
        stmt = select(func.count()).select_from(Alert).where(*conditions)  # type: ignore[arg-type]
        return int(self._s.scalar(stmt) or 0)

    def acknowledge_all(self, user: str, now: datetime) -> int:
        result = self._s.execute(
            update(Alert)
            .where(Alert.resolved_at.is_(None), Alert.acknowledged_at.is_(None))
            .values(acknowledged_at=now, acknowledged_by=user)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def open_for_device(self, device_id: int, kind: str) -> list[Alert]:
        return list(
            self._s.scalars(
                select(Alert).where(
                    Alert.device_id == device_id, Alert.kind == kind, Alert.resolved_at.is_(None)
                )
            )
        )

    def rules(self) -> list[AlertRule]:
        return list(self._s.scalars(select(AlertRule).order_by(AlertRule.kind)))

    def rule(self, kind: str) -> AlertRule | None:
        return self._s.get(AlertRule, kind)

    def add_rule(self, rule: AlertRule) -> None:
        self._s.add(rule)
