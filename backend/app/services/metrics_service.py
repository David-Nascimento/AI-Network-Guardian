"""Registro, consulta, agregação e retenção de métricas de rede."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.collectors import ProbeResult
from app.core.exceptions import DomainValidationError
from app.models import NetworkMetric
from app.repositories import MetricAggregate, MetricRepository
from app.schemas import MetricPoint, MetricsComparison, MetricsSummary

MAX_POINTS = 20_000


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


class MetricsService:
    def __init__(self, session: Session) -> None:
        self._metrics = MetricRepository(session)

    def record(self, target_id: int, result: ProbeResult, *, ts: datetime | None = None) -> None:
        self._metrics.add(
            NetworkMetric(
                target_id=target_id,
                ts=ts or datetime.now(UTC),
                success=result.success,
                sent=result.sent,
                received=result.received,
                latency_min_ms=result.latency_min_ms,
                latency_avg_ms=result.latency_avg_ms,
                latency_max_ms=result.latency_max_ms,
                jitter_ms=result.jitter_ms,
                packet_loss_pct=result.packet_loss_pct,
                error=(result.error or None) and result.error[:200],
            )
        )

    def history(
        self, *, hours: int, target_id: int | None, bucket_minutes: int | None
    ) -> list[MetricPoint]:
        until = datetime.now(UTC)
        rows = self._metrics.range(
            since=until - timedelta(hours=hours), until=until, target_id=target_id, limit=MAX_POINTS
        )
        if not bucket_minutes:
            return [
                MetricPoint(
                    ts=r.ts,
                    target_id=r.target_id,
                    latency_avg_ms=r.latency_avg_ms,
                    latency_max_ms=r.latency_max_ms,
                    jitter_ms=r.jitter_ms,
                    packet_loss_pct=r.packet_loss_pct,
                    samples=1,
                )
                for r in rows
            ]
        width = bucket_minutes * 60
        buckets: dict[tuple[int, int], list[NetworkMetric]] = defaultdict(list)
        for r in rows:
            buckets[(r.target_id, int(r.ts.timestamp()) // width)].append(r)
        points = []
        for (tid, slot), group in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            maxima = [g.latency_max_ms for g in group if g.latency_max_ms is not None]
            points.append(
                MetricPoint(
                    ts=datetime.fromtimestamp(slot * width, UTC),
                    target_id=tid,
                    latency_avg_ms=_avg(
                        [g.latency_avg_ms for g in group if g.latency_avg_ms is not None]
                    ),
                    latency_max_ms=max(maxima) if maxima else None,
                    jitter_ms=_avg([g.jitter_ms for g in group if g.jitter_ms is not None]),
                    packet_loss_pct=_avg([g.packet_loss_pct for g in group]) or 0.0,
                    samples=len(group),
                )
            )
        return points

    def summary(self, *, hours: int, target_id: int | None) -> MetricsSummary:
        until = datetime.now(UTC)
        return self._summarize(until - timedelta(hours=hours), until, target_id)

    def compare(self, *, hours: int, target_id: int | None) -> MetricsComparison:
        if hours < 1:
            raise DomainValidationError("'hours' deve ser >= 1")
        now = datetime.now(UTC)
        window = timedelta(hours=hours)
        current = self._summarize(now - window, now, target_id)
        previous = self._summarize(now - 2 * window, now - window, target_id)

        def delta(a: float | None, b: float | None) -> float | None:
            return None if a is None or b is None else round(a - b, 3)

        return MetricsComparison(
            current=current,
            previous=previous,
            latency_avg_delta_ms=delta(current.latency_avg_ms, previous.latency_avg_ms),
            packet_loss_delta_pct=delta(current.packet_loss_avg_pct, previous.packet_loss_avg_pct),
            availability_delta_pct=delta(current.availability_pct, previous.availability_pct),
        )

    def purge(self, retention_days: int) -> int:
        return self._metrics.delete_older_than(datetime.now(UTC) - timedelta(days=retention_days))

    def _summarize(self, since: datetime, until: datetime, target_id: int | None) -> MetricsSummary:
        agg: MetricAggregate = self._metrics.aggregate(
            since=since, until=until, target_id=target_id
        )
        availability = round(100 * agg.successes / agg.samples, 2) if agg.samples else None
        return MetricsSummary(
            since=since,
            until=until,
            samples=agg.samples,
            availability_pct=availability,
            latency_min_ms=_round(agg.latency_min_ms),
            latency_avg_ms=_round(agg.latency_avg_ms),
            latency_max_ms=_round(agg.latency_max_ms),
            jitter_avg_ms=_round(agg.jitter_avg_ms),
            packet_loss_avg_pct=_round(agg.packet_loss_avg_pct),
        )
