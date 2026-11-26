"""Transforma medições brutas em janelas de tempo (uma linha por destino e janela)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import fmean


@dataclass(frozen=True, slots=True)
class Sample:
    """Uma medição já lida do banco (independe do ORM, para testar sem banco)."""

    ts: datetime
    latency_avg_ms: float | None
    latency_max_ms: float | None
    jitter_ms: float | None
    packet_loss_pct: float


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime
    values: tuple[float, float, float, float]  # latência média, latência máx., jitter, perda %


def _floor(ts: datetime, minutes: int) -> datetime:
    ts = ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
    return ts.replace(minute=ts.minute - ts.minute % minutes, second=0, microsecond=0)


def build_windows(samples: Iterable[Sample], minutes: int = 5) -> list[Window]:
    """Agrupa em janelas de `minutes`. Janelas sem nenhuma resposta (queda total) ficam de fora:
    quedas já são tratadas como incidentes; aqui interessa o comportamento quando há resposta."""
    buckets: dict[datetime, list[Sample]] = defaultdict(list)
    for s in samples:
        buckets[_floor(s.ts, minutes)].append(s)
    windows: list[Window] = []
    for start in sorted(buckets):
        rows = buckets[start]
        avg = [r.latency_avg_ms for r in rows if r.latency_avg_ms is not None]
        peak = [r.latency_max_ms for r in rows if r.latency_max_ms is not None]
        if not avg or not peak:
            continue
        jitter = [r.jitter_ms for r in rows if r.jitter_ms is not None]
        windows.append(
            Window(
                start,
                (
                    fmean(avg),
                    max(peak),
                    fmean(jitter) if jitter else 0.0,
                    fmean(r.packet_loss_pct for r in rows),
                ),
            )
        )
    return windows
