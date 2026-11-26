from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.jobs import run_anomaly_scan
from app.models import Anomaly, NetworkMetric
from app.services import AlertService, AnomalyService
from tests.conftest import add_target

API = "/api/v1"
NOW = datetime(2026, 11, 25, 12, 2, tzinfo=UTC)


def seed(client: TestClient, target_id: int, *, spike_last: bool, windows: int = 80) -> None:
    rnd = random.Random(3)
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        for i in range(windows):
            start = NOW.replace(minute=0, second=0) - timedelta(minutes=5 * (windows - i))
            bad = spike_last and i >= windows - 2
            for k in range(3):
                avg = 150.0 if bad else 12 + rnd.uniform(-1.5, 1.5)
                s.add(
                    NetworkMetric(
                        target_id=target_id,
                        ts=start + timedelta(seconds=40 * k),
                        success=True,
                        sent=4,
                        received=4,
                        latency_min_ms=avg - 1,
                        latency_avg_ms=avg,
                        latency_max_ms=avg + 4,
                        jitter_ms=1.5,
                        packet_loss_pct=0.0,
                    )
                )
        s.commit()


def run(client: TestClient, settings: Settings) -> None:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        alerts = AlertService(s)
        AnomalyService(s, settings, alerts).scan(now=NOW)
        s.commit()


def test_status_reports_not_ready_without_data(client: TestClient, auth: dict[str, str]) -> None:
    add_target(client, auth, "Cloudflare", "1.1.1.1")
    st = client.get(f"{API}/ml/status", headers=auth).json()
    assert st["enabled"] is True and st["effective_method"] is None
    assert st["targets"][0]["ready"] is False and st["targets"][0]["windows"] == 0


def test_no_data_means_no_anomaly_and_no_alert(
    client: TestClient, auth: dict[str, str], settings: Settings
) -> None:
    add_target(client, auth, "Cloudflare", "1.1.1.1")
    run(client, settings)
    assert client.get(f"{API}/ml/anomalies", headers=auth).json() == []


def test_spike_creates_anomaly_and_alert_then_resolves(
    client: TestClient, auth: dict[str, str], settings: Settings
) -> None:
    tid = add_target(client, auth, "Cloudflare", "1.1.1.1")
    seed(client, tid, spike_last=True)
    run(client, settings)
    run(client, settings)  # reexecutar não duplica
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        rows = list(s.scalars(select(Anomaly)))
    assert 1 <= len(rows) <= 2 and all(r.target_id == tid for r in rows)
    assert "latência média" in rows[0].deviations[0]
    alerts = [a for a in client.get(f"{API}/alerts", headers=auth).json() if a["kind"] == "anomaly"]
    assert len(alerts) == 1 and "não indica a causa" in alerts[0]["message"]

    # a rede volta ao normal: novas janelas boas resolvem o alerta
    later = NOW + timedelta(minutes=10)
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        for m in range(3):
            for k in range(3):
                s.add(
                    NetworkMetric(
                        target_id=tid,
                        ts=NOW + timedelta(minutes=5 * m, seconds=40 * k),
                        success=True,
                        sent=4,
                        received=4,
                        latency_min_ms=11,
                        latency_avg_ms=12,
                        latency_max_ms=15,
                        jitter_ms=1.5,
                        packet_loss_pct=0.0,
                    )
                )
        s.commit()
        AnomalyService(s, settings, AlertService(s)).scan(now=later + timedelta(minutes=10))
        s.commit()
    assert [
        a for a in client.get(f"{API}/alerts", headers=auth).json() if a["kind"] == "anomaly"
    ] == []


def test_status_ready_and_list_endpoint(
    client: TestClient, auth: dict[str, str], settings: Settings
) -> None:
    tid = add_target(client, auth, "Cloudflare", "1.1.1.1")
    seed(client, tid, spike_last=False)
    st = client.get(f"{API}/ml/status", headers=auth).json()
    assert st["targets"][0]["ready"] is True and st["effective_method"] in {
        "robust_zscore",
        "isolation_forest",
    }
    assert client.get(f"{API}/ml/anomalies", headers=auth).status_code == 200
    assert client.get(f"{API}/ml/status").status_code == 401


def test_job_wrapper_never_raises(client: TestClient, settings: Settings) -> None:
    class Boom:
        def __call__(self) -> None:
            raise RuntimeError("falha simulada")

    run_anomaly_scan(Boom(), settings)  # type: ignore[arg-type]
