from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import cast as typing_cast

from sqlalchemy import CursorResult, Integer, cast, delete, func, select
from sqlalchemy.orm import Session

from app.models import NetworkMetric


@dataclass(frozen=True, slots=True)
class MetricAggregate:
    samples: int
    successes: int
    latency_min_ms: float | None
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_avg_ms: float | None
    packet_loss_avg_pct: float | None


class MetricRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, metric: NetworkMetric) -> NetworkMetric:
        self._s.add(metric)
        self._s.flush()
        return metric

    def latest(self, target_id: int) -> NetworkMetric | None:
        return self._s.scalar(
            select(NetworkMetric)
            .where(NetworkMetric.target_id == target_id)
            .order_by(NetworkMetric.ts.desc(), NetworkMetric.id.desc())
            .limit(1)
        )

    def last_n(self, target_id: int, n: int) -> list[NetworkMetric]:
        return list(
            self._s.scalars(
                select(NetworkMetric)
                .where(NetworkMetric.target_id == target_id)
                .order_by(NetworkMetric.ts.desc(), NetworkMetric.id.desc())
                .limit(n)
            )
        )

    def range(
        self, *, since: datetime, until: datetime, target_id: int | None, limit: int
    ) -> list[NetworkMetric]:
        stmt = (
            select(NetworkMetric)
            .where(NetworkMetric.ts >= since, NetworkMetric.ts < until)
            .order_by(NetworkMetric.ts)
            .limit(limit)
        )
        if target_id is not None:
            stmt = stmt.where(NetworkMetric.target_id == target_id)
        return list(self._s.scalars(stmt))

    def aggregate(
        self, *, since: datetime, until: datetime, target_id: int | None
    ) -> MetricAggregate:
        m = NetworkMetric
        stmt = select(
            func.count(m.id),
            func.coalesce(func.sum(cast(m.success, Integer)), 0),
            func.min(m.latency_min_ms),
            func.avg(m.latency_avg_ms),
            func.max(m.latency_max_ms),
            func.avg(m.jitter_ms),
            func.avg(m.packet_loss_pct),
        ).where(m.ts >= since, m.ts < until)
        if target_id is not None:
            stmt = stmt.where(m.target_id == target_id)
        row = self._s.execute(stmt).one()
        return MetricAggregate(
            samples=int(row[0]),
            successes=int(row[1]),
            latency_min_ms=row[2],
            latency_avg_ms=row[3],
            latency_max_ms=row[4],
            jitter_avg_ms=row[5],
            packet_loss_avg_pct=row[6],
        )

    def delete_older_than(self, cutoff: datetime) -> int:
        result = self._s.execute(delete(NetworkMetric).where(NetworkMetric.ts < cutoff))
        return int(typing_cast(CursorResult[Any], result).rowcount or 0)
