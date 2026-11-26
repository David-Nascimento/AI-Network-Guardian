"""Detectores de anomalia. Dois métodos, ambos sobre a "linha de base" do próprio destino:

* ``isolation_forest`` (scikit-learn, extra opcional ``.[ml]``);
* ``robust_zscore`` (mediana/MAD, Python puro) — usado quando o scikit-learn não está instalado.

Em ambos, só vira anomalia se alguma medida se afastar de verdade da mediana (|z| ≥ 3,5):
isso evita falso alarme quando os dados são quase constantes. O resultado descreve *o que*
se afastou do normal, nunca *por quê* — causa não é algo que estas medições provem.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from statistics import median
from typing import Protocol

FEATURES: tuple[str, ...] = ("latency_avg_ms", "latency_max_ms", "jitter_ms", "packet_loss_pct")
LABELS = {
    "latency_avg_ms": ("latência média", " ms"),
    "latency_max_ms": ("latência máxima", " ms"),
    "jitter_ms": ("jitter", " ms"),
    "packet_loss_pct": ("perda de pacotes", "%"),
}
Z_LIMIT = 3.5
_MAD_TO_SIGMA = 1.4826
_MIN_SCALE = {
    "latency_avg_ms": 1.0,
    "latency_max_ms": 2.0,
    "jitter_ms": 1.0,
    "packet_loss_pct": 2.0,
}
_IF_MIN_ROWS = 20


def sklearn_available() -> bool:
    return importlib.util.find_spec("sklearn") is not None


@dataclass(frozen=True, slots=True)
class Deviation:
    feature: str
    value: float
    normal: float
    z: float

    def text(self) -> str:
        label, unit = LABELS[self.feature]
        direction = "acima" if self.z > 0 else "abaixo"
        return f"{label} {self.value:.1f}{unit} ({direction} do normal ≈ {self.normal:.1f}{unit})"


@dataclass(frozen=True, slots=True)
class Verdict:
    anomalous: bool
    score: float
    deviations: tuple[Deviation, ...]


class Baseline:
    """Mediana e escala robusta (MAD) de cada medida, com piso para não dividir por ~0."""

    def __init__(self, rows: list[tuple[float, ...]]) -> None:
        columns = list(zip(*rows, strict=True))
        self.medians = [median(c) for c in columns]
        self.scales = []
        for name, col, med in zip(FEATURES, columns, self.medians, strict=True):
            mad = median(abs(v - med) for v in col) * _MAD_TO_SIGMA
            self.scales.append(max(mad, abs(med) * 0.1, _MIN_SCALE[name]))

    def z(self, row: tuple[float, ...]) -> list[float]:
        return [(v - m) / s for v, m, s in zip(row, self.medians, self.scales, strict=True)]

    def deviations(self, row: tuple[float, ...]) -> tuple[Deviation, ...]:
        zs = self.z(row)
        found = [
            Deviation(name, value, med, z)
            for name, value, med, z in zip(FEATURES, row, self.medians, zs, strict=True)
            if abs(z) >= Z_LIMIT
        ]
        return tuple(sorted(found, key=lambda d: abs(d.z), reverse=True))


class Detector(Protocol):
    method: str

    def fit(self, rows: list[tuple[float, ...]]) -> None: ...

    def judge(self, row: tuple[float, ...]) -> Verdict: ...


class RobustZScoreDetector:
    method = "robust_zscore"

    def __init__(self) -> None:
        self._base: Baseline | None = None

    def fit(self, rows: list[tuple[float, ...]]) -> None:
        self._base = Baseline(rows)

    def judge(self, row: tuple[float, ...]) -> Verdict:
        assert self._base is not None, "fit() primeiro"
        devs = self._base.deviations(row)
        return Verdict(bool(devs), max((abs(z) for z in self._base.z(row)), default=0.0), devs)


class IsolationForestDetector:
    method = "isolation_forest"

    def __init__(self) -> None:
        self._base: Baseline | None = None
        self._forest: object | None = None

    def fit(self, rows: list[tuple[float, ...]]) -> None:
        from sklearn.ensemble import IsolationForest  # noqa: PLC0415 - extra opcional

        self._base = Baseline(rows)
        forest = IsolationForest(n_estimators=100, contamination=0.02, random_state=0)
        forest.fit([self._base.z(r) for r in rows])
        self._forest = forest

    def judge(self, row: tuple[float, ...]) -> Verdict:
        assert self._base is not None
        assert self._forest is not None, "fit() primeiro"
        z = [self._base.z(row)]
        outlier = int(self._forest.predict(z)[0]) == -1  # type: ignore[attr-defined]
        score = float(-self._forest.score_samples(z)[0])  # type: ignore[attr-defined]
        devs = self._base.deviations(row)
        return Verdict(outlier and bool(devs), score, devs if outlier else ())


def make_detector(preferred: str = "auto", *, rows: int = 0) -> Detector:
    """`auto`: Isolation Forest se o scikit-learn existir e houver dados suficientes."""
    if preferred == "isolation_forest" and not sklearn_available():
        raise RuntimeError('scikit-learn não instalado (pip install -e ".[ml]")')
    wants_forest = preferred == "isolation_forest" or (
        preferred == "auto" and sklearn_available() and rows >= _IF_MIN_ROWS
    )
    return IsolationForestDetector() if wants_forest else RobustZScoreDetector()
