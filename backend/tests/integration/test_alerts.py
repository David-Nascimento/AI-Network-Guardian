from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.collectors.arp_collector import DiscoveredHost
from app.core.config import Settings
from app.core.security import hash_password
from app.models import User
from tests.conftest import FakeProbe, FakeScanner, add_target
from tests.integration.test_api import cycle
from tests.integration.test_devices import GW, PHONE, scan

API = "/api/v1"


def alerts(client: TestClient, auth: dict[str, str], status: str = "active") -> list[dict]:
    r = client.get(f"{API}/alerts", params={"status": status}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_new_device_alert_is_created_once_and_resolved_when_marked_known(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    scan(client, auth, scanner, GW, PHONE)  # outra varredura não duplica
    active = alerts(client, auth)
    assert len(active) == 2 and {a["kind"] for a in active} == {"new_device"}
    assert all(a["status"] == "new" for a in active)
    assert client.get(f"{API}/alerts/summary", headers=auth).json()["new"] == 2

    devices = {d["mac"]: d for d in client.get(f"{API}/devices", headers=auth).json()}
    r = client.patch(
        f"{API}/devices/{devices[PHONE.mac]['id']}", json={"is_known": True}, headers=auth
    )
    assert r.status_code == 200
    assert [a["device_id"] for a in alerts(client, auth)] == [devices[GW.mac]["id"]]
    assert len(alerts(client, auth, "resolved")) == 1

    client.post(f"{API}/devices/mark-all-known", headers=auth)
    assert alerts(client, auth) == []


def test_offline_alert_only_for_known_devices_and_when_rule_enabled(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    client.post(f"{API}/devices/mark-all-known", headers=auth)
    # regra desligada por padrão: nenhum alerta de "offline"
    scan(client, auth, scanner, GW)
    scan(client, auth, scanner, GW)
    assert alerts(client, auth, "all") and all(
        a["kind"] != "known_device_offline" for a in alerts(client, auth, "all")
    )

    r = client.patch(
        f"{API}/alerts/rules/known_device_offline", json={"enabled": True}, headers=auth
    )
    assert r.status_code == 200 and r.json()["enabled"] is True
    scan(client, auth, scanner, GW, PHONE)
    scan(client, auth, scanner, GW)
    scan(client, auth, scanner, GW)
    offline = [a for a in alerts(client, auth) if a["kind"] == "known_device_offline"]
    assert len(offline) == 1
    scan(client, auth, scanner, GW, PHONE)  # voltou: o alerta se resolve sozinho
    assert not [a for a in alerts(client, auth) if a["kind"] == "known_device_offline"]


def test_disabled_rule_creates_no_alert(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    client.patch(f"{API}/alerts/rules/new_device", json={"enabled": False}, headers=auth)
    scan(client, auth, scanner, PHONE)
    assert alerts(client, auth, "all") == []


def test_acknowledge_one_and_all(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    first = alerts(client, auth)[0]
    r = client.post(f"{API}/alerts/{first['id']}/ack", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"
    assert r.json()["acknowledged_by"]
    summary = client.get(f"{API}/alerts/summary", headers=auth).json()
    assert (summary["new"], summary["acknowledged"]) == (1, 1)
    assert client.post(f"{API}/alerts/ack-all", headers=auth).json()["updated"] == 1
    assert client.get(f"{API}/alerts/summary", headers=auth).json()["new"] == 0
    assert client.post(f"{API}/alerts/9999/ack", headers=auth).status_code == 404


def test_rules_list_and_unknown_rule(client: TestClient, auth: dict[str, str]) -> None:
    rules = {r["kind"]: r for r in client.get(f"{API}/alerts/rules", headers=auth).json()}
    assert rules["new_device"]["enabled"] is True
    assert rules["known_device_offline"]["enabled"] is False
    r = client.patch(f"{API}/alerts/rules/inexistente", json={"enabled": True}, headers=auth)
    assert r.status_code == 404


def test_alert_writes_require_admin(client: TestClient, auth: dict[str, str]) -> None:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        s.add(User(username="leitor", password_hash=hash_password("senha-leitor-1"), role="viewer"))
        s.commit()
    token = client.post(
        f"{API}/auth/login", json={"username": "leitor", "password": "senha-leitor-1"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get(f"{API}/alerts", headers=h).status_code == 200
    assert client.post(f"{API}/alerts/ack-all", headers=h).status_code == 403
    assert (
        client.patch(
            f"{API}/alerts/rules/new_device", json={"enabled": False}, headers=h
        ).status_code
        == 403
    )
    assert client.get(f"{API}/alerts").status_code == 401


def test_network_incident_opens_and_resolves_alert(
    client: TestClient, auth: dict[str, str], settings: Settings, probe: FakeProbe
) -> None:
    add_target(client, auth, "Roteador", "192.168.100.1", kind="gateway")
    add_target(client, auth, "Cloudflare", "1.1.1.1")
    cycle(client, settings, probe, times=1)
    assert [a for a in alerts(client, auth) if a["kind"] == "network_incident"] == []

    probe.down = {"192.168.100.1", "1.1.1.1"}
    cycle(client, settings, probe, times=3)
    incidents = [a for a in alerts(client, auth) if a["kind"] == "network_incident"]
    assert incidents, "uma queda deveria gerar alerta"

    probe.down = set()
    cycle(client, settings, probe, times=3)
    assert [a for a in alerts(client, auth) if a["kind"] == "network_incident"] == []
    assert any(a["kind"] == "network_incident" for a in alerts(client, auth, "resolved"))


# ---- WebSocket ------------------------------------------------------------
def token_of(auth: dict[str, str]) -> str:
    return auth["Authorization"].removeprefix("Bearer ")


def test_websocket_rejects_missing_or_bad_token(client: TestClient) -> None:
    with client.websocket_connect(f"{API}/ws") as ws:
        ws.send_json({"type": "auth", "token": "invalido"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401
    with client.websocket_connect(f"{API}/ws") as ws:
        ws.send_json({"type": "ping"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_websocket_receives_events_from_scan_and_alerts(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    with client.websocket_connect(f"{API}/ws") as ws:
        ws.send_json({"type": "auth", "token": token_of(auth)})
        assert ws.receive_json()["type"] == "ready"
        scan(client, auth, scanner, DiscoveredHost("192.168.100.50", "aa:bb:cc:00:00:50"))
        seen = set()
        for _ in range(6):
            seen.add(ws.receive_json()["type"])
            if {"alert.created", "devices.updated"} <= seen:
                break
        assert {"alert.created", "devices.updated"} <= seen
