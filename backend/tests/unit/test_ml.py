from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from app.ml import Baseline, build_windows, make_detector, sklearn_available
from app.ml.detector import IsolationForestDetector, RobustZScoreDetector
from app.ml.features import Sample

T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def normal_rows(n: int = 200, seed: int = 1) -> list[tuple[float, float, float, float]]:
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        avg = 12 + rnd.uniform(-1.5, 1.5)
        rows.append((avg, avg + 6 + rnd.uniform(0, 3), 1.5 + rnd.uniform(0, 1), 0.0))
    return rows


def test_windows_aggregate_and_skip_total_outage() -> None:
    samples = [
        Sample(T0 + timedelta(seconds=10), 10.0, 14.0, 1.0, 0.0),
        Sample(T0 + timedelta(seconds=40), 20.0, 30.0, 3.0, 25.0),
        Sample(T0 + timedelta(minutes=5, seconds=5), None, None, None, 100.0),  # queda total
        Sample(T0 + timedelta(minutes=10), 11.0, 12.0, None, 0.0),
    ]
    windows = build_windows(samples, 5)
    assert [w.start for w in windows] == [T0, T0 + timedelta(minutes=10)]
    assert windows[0].values == (15.0, 30.0, 2.0, 12.5)
    assert windows[1].values[2] == 0.0  # sem jitter medido: 0, não inventado


def test_baseline_floor_avoids_division_by_zero() -> None:
    base = Baseline([(10.0, 12.0, 1.0, 0.0)] * 30)
    assert all(s > 0 for s in base.scales)
    assert base.deviations((10.0, 12.0, 1.0, 0.0)) == ()


@pytest.mark.parametrize("detector_cls", [RobustZScoreDetector, IsolationForestDetector])
def test_detectors_flag_real_deviation_and_ignore_normal(detector_cls: type) -> None:
    if detector_cls is IsolationForestDetector and not sklearn_available():
        pytest.skip("scikit-learn não instalado")
    rows = normal_rows()
    det = detector_cls()
    det.fit(rows)
    assert not det.judge((12.2, 19.0, 2.0, 0.0)).anomalous
    spike = det.judge((95.0, 180.0, 40.0, 0.0))
    assert spike.anomalous and spike.deviations
    assert "latência média" in spike.deviations[0].text() + " ".join(
        d.text() for d in spike.deviations
    )


def test_constant_data_does_not_alarm_on_tiny_change() -> None:
    det = RobustZScoreDetector()
    det.fit([(10.0, 12.0, 1.0, 0.0)] * 60)
    assert not det.judge((10.6, 12.5, 1.2, 0.0)).anomalous  # dentro do piso de escala
    assert det.judge((10.0, 12.0, 1.0, 40.0)).anomalous  # perda de 40% em base zerada


def test_make_detector_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    assert make_detector("robust_zscore").method == "robust_zscore"
    assert make_detector("auto", rows=5).method == "robust_zscore"  # poucos dados
    monkeypatch.setattr("app.ml.detector.sklearn_available", lambda: False)
    assert make_detector("auto", rows=500).method == "robust_zscore"
    with pytest.raises(RuntimeError):
        make_detector("isolation_forest")
