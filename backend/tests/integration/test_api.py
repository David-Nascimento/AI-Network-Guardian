from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.collectors import build_probe_registry
from app.core.config import Settings
from app.core.security import hash_password
from app.jobs import run_collection_cycle, run_retention
from app.models import User
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER, FakeProbe, add_target

BACKEND = Path(__file__).resolve().parents[2]


def cycle(client: TestClient, settings: Settings, probe: FakeProbe, times: int = 1) -> None:
    registry = {"icmp": probe, "tcp": probe, "dns": probe}
    for _ in range(times):
        run_collection_cycle(client.app.state.session_factory, settings, registry)  # type: ignore[attr-defined]


# ---- saúde e auth --------------------------------------------------------
def test_liveness_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"
    assert "x-request-id" in r.headers


def test_readiness_503_when_database_unavailable(client: TestClient, engine: Engine) -> None:
    engine.dispose()
    client.app.state.session_factory = lambda: (_ for _ in ()).throw(RuntimeError("db off"))  # type: ignore[attr-defined]
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["checks"]["database"] == "unavailable"


def test_login_wrong_password_and_unknown_user_look_identical(client: TestClient) -> None:
    a = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": "errada"})
    b = client.post("/api/v1/auth/login", json={"username": "ninguem", "password": "errada"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_protected_routes_require_token(client: TestClient) -> None:
    for path in ("/api/v1/network/status", "/api/v1/metrics/summary", "/api/v1/auth/me"):
        assert client.get(path).status_code == 401
    bad = {"Authorization": "Bearer lixo"}
    assert client.get("/api/v1/auth/me", headers=bad).status_code == 401


def test_me_returns_user(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/api/v1/auth/me", headers=auth).json() == {
        "username": ADMIN_USER,
        "role": "admin",
    }


def test_login_is_rate_limited(client: TestClient) -> None:
    codes = [
        client.post(
            "/api/v1/auth/login", json={"username": ADMIN_USER, "password": "x"}
        ).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    blocked = client.post(
        "/api/v1/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}
    )
    assert blocked.status_code == 429 and "retry-after" in blocked.headers


def test_validation_error_shape(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# ---- destinos ------------------------------------------------------------
def test_target_crud_and_duplicates(client: TestClient, auth: dict[str, str]) -> None:
    tid = add_target(client, auth, "Cloudflare", "1.1.1.1")
    dup = client.post(
        "/api/v1/network/targets",
        json={"name": "Cloudflare", "host": "9.9.9.9", "kind": "external", "method": "icmp"},
        headers=auth,
    )
    assert dup.status_code == 409
    r = client.patch(f"/api/v1/network/targets/{tid}", json={"enabled": False}, headers=auth)
    assert r.json()["enabled"] is False
    assert client.delete(f"/api/v1/network/targets/{tid}", headers=auth).status_code == 204
    assert client.delete(f"/api/v1/network/targets/{tid}", headers=auth).status_code == 404
    assert client.get("/api/v1/network/targets", headers=auth).json() == []


def test_target_rejects_ssrf_and_incoherent_input(client: TestClient, auth: dict[str, str]) -> None:
    def post(**over: object) -> int:
        body = {"name": "x", "host": "1.1.1.1", "kind": "external", "method": "icmp", **over}
        return client.post("/api/v1/network/targets", json=body, headers=auth).status_code

    assert post(host="169.254.169.254") == 422
    assert post(host="127.0.0.1") == 422
    assert post(host="10.1.2.3") == 201  # privado dentro das faixas autorizadas
    assert post(name="y", method="tcp") == 422  # tcp sem porta
    assert post(name="z", method="icmp", port=80) == 422
    assert post(name="w", kind="dns", method="icmp") == 422
    assert post(name="v", host="localhost") == 422  # sem domínio completo


def test_viewer_cannot_manage_targets(client: TestClient, session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        s.add(User(username="leitor", password_hash=hash_password("senha-leitor-1"), role="viewer"))
        s.commit()
    token = client.post(
        "/api/v1/auth/login", json={"username": "leitor", "password": "senha-leitor-1"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"name": "n", "host": "1.1.1.1", "kind": "external", "method": "icmp"}
    assert client.post("/api/v1/network/targets", json=body, headers=headers).status_code == 403
    assert client.get("/api/v1/network/targets", headers=headers).status_code == 200


# ---- coleta, status e eventos -------------------------------------------
def test_status_unknown_before_first_cycle(client: TestClient, auth: dict[str, str]) -> None:
    add_target(client, auth, "A", "1.1.1.1")
    assert client.get("/api/v1/network/status", headers=auth).json()["state"] == "unknown"


def test_healthy_cycle_records_metrics(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    add_target(client, auth, "A", "1.1.1.1")
    cycle(client, settings, probe)
    st = client.get("/api/v1/network/status", headers=auth).json()
    assert st["state"] == "online" and st["active_events"] == []
    assert st["targets"][0]["latency_avg_ms"] == 12.0
    summary = client.get("/api/v1/metrics/summary?hours=1", headers=auth).json()
    assert summary["samples"] == 1 and summary["availability_pct"] == 100.0
    assert summary["latency_min_ms"] == 10.0 and summary["latency_max_ms"] == 15.0


def test_single_target_failure_vs_general_outage_with_recovery(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    add_target(client, auth, "GW", "192.168.1.1", kind="gateway")
    add_target(client, auth, "A", "1.1.1.1")
    add_target(client, auth, "B", "8.8.8.8")

    probe.down = {"1.1.1.1"}
    cycle(client, settings, probe, times=1)  # abaixo do limiar (2): sem evento ainda
    assert client.get("/api/v1/network/events", headers=auth).json() == []
    cycle(client, settings, probe, times=1)
    events = client.get("/api/v1/network/events?active_only=true", headers=auth).json()
    assert [e["event_type"] for e in events] == ["target_down"]
    assert client.get("/api/v1/network/status", headers=auth).json()["state"] == "degraded"

    probe.down = {"1.1.1.1", "8.8.8.8"}
    cycle(client, settings, probe, times=2)
    active = client.get("/api/v1/network/events?active_only=true", headers=auth).json()
    assert [e["event_type"] for e in active] == ["internet_down"]
    assert client.get("/api/v1/network/status", headers=auth).json()["state"] == "offline"

    probe.down = set()
    cycle(client, settings, probe, times=1)
    assert client.get("/api/v1/network/events?active_only=true", headers=auth).json() == []
    history = client.get("/api/v1/network/events", headers=auth).json()
    assert len(history) == 2 and all(e["ended_at"] for e in history)


def test_repeated_failures_do_not_duplicate_events(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    add_target(client, auth, "A", "1.1.1.1")
    add_target(client, auth, "B", "8.8.8.8")
    probe.down = {"1.1.1.1"}
    cycle(client, settings, probe, times=6)
    assert len(client.get("/api/v1/network/events", headers=auth).json()) == 1


def test_unavailable_collector_creates_no_data_and_no_incident(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    add_target(client, auth, "A", "1.1.1.1")
    add_target(client, auth, "B", "8.8.8.8")
    probe.unavailable = True
    cycle(client, settings, probe, times=4)
    assert client.get("/api/v1/network/events", headers=auth).json() == []
    assert client.get("/api/v1/metrics/summary", headers=auth).json()["samples"] == 0


def test_disabled_targets_are_not_probed(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    tid = add_target(client, auth, "A", "1.1.1.1")
    client.patch(f"/api/v1/network/targets/{tid}", json={"enabled": False}, headers=auth)
    cycle(client, settings, probe)
    assert probe.calls == []


# ---- métricas ------------------------------------------------------------
def test_history_bucketing_and_compare(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    tid = add_target(client, auth, "A", "1.1.1.1")
    cycle(client, settings, probe, times=3)
    raw = client.get(f"/api/v1/metrics/history?hours=1&target_id={tid}", headers=auth).json()
    assert len(raw) == 3
    bucketed = client.get("/api/v1/metrics/history?hours=1&bucket_minutes=60", headers=auth).json()
    assert sum(p["samples"] for p in bucketed) == 3 and len(bucketed) <= 2
    cmp = client.get("/api/v1/metrics/compare?hours=1", headers=auth).json()
    assert cmp["current"]["samples"] == 3 and cmp["previous"]["samples"] == 0
    assert cmp["latency_avg_delta_ms"] is None


def test_metrics_query_validation(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/api/v1/metrics/summary?hours=0", headers=auth).status_code == 422
    assert client.get("/api/v1/metrics/history?target_id=0", headers=auth).status_code == 422


def test_retention_purges_old_samples(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe, engine: Engine
) -> None:
    add_target(client, auth, "A", "1.1.1.1")
    cycle(client, settings, probe, times=2)
    with engine.begin() as conn:
        conn.execute(text("UPDATE network_metrics SET ts = '2000-01-01 00:00:00' WHERE id = 1"))
    removed = run_retention(client.app.state.session_factory, settings)  # type: ignore[attr-defined]
    assert removed == 1
    assert client.get("/api/v1/metrics/summary?hours=1", headers=auth).json()["samples"] == 1


def test_real_probe_registry_has_all_methods() -> None:
    assert set(build_probe_registry()) == {"icmp", "tcp", "dns"}


# ---- migrações -----------------------------------------------------------
def test_alembic_migrations_match_models(tmp_path: Path) -> None:
    env = {"NG_DATABASE_URL": f"sqlite:///{tmp_path / 'm.db'}", "PATH": "/usr/bin:/bin"}
    for args in (["upgrade", "head"], ["check"]):
        run = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stderr
