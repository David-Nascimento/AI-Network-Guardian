"""Tipos comuns a todos os coletores de latência."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol


class CollectorUnavailableError(RuntimeError):
    """O coletor não pôde operar (ex.: binário `ping` ausente). Não indica falha de rede."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    sent: int
    received: int
    latency_min_ms: float | None = None
    latency_avg_ms: float | None = None
    latency_max_ms: float | None = None
    jitter_ms: float | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.received > 0

    @property
    def packet_loss_pct(self) -> float:
        if self.sent <= 0:
            return 100.0
        return round(100.0 * (self.sent - self.received) / self.sent, 2)

    @classmethod
    def from_rtts(cls, sent: int, rtts: Sequence[float], error: str | None = None) -> ProbeResult:
        """Constrói o resultado a partir dos RTTs (ms) das respostas recebidas."""
        if not rtts:
            return cls(sent=sent, received=0, error=error or "sem resposta")
        diffs = [abs(b - a) for a, b in pairwise(rtts)]
        return cls(
            sent=sent,
            received=len(rtts),
            latency_min_ms=round(min(rtts), 3),
            latency_avg_ms=round(sum(rtts) / len(rtts), 3),
            latency_max_ms=round(max(rtts), 3),
            jitter_ms=round(sum(diffs) / len(diffs), 3) if diffs else None,
            error=error,
        )


class Probe(Protocol):
    def run(self, host: str, *, port: int | None, count: int, timeout: float) -> ProbeResult: ...
