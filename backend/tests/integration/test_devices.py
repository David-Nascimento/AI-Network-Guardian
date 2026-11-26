from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.collectors.arp_collector import DiscoveredHost
from app.core.config import Settings
from app.core.security import hash_password
from app.models import Device, User
from tests.conftest import FakeProbe, FakeScanner, add_target
from tests.integration.test_api import cycle

GW = DiscoveredHost("192.168.100.1", "f4:b5:20:48:72:b4", "roteador.lan")
PHONE = DiscoveredHost("192.168.100.20", "da:a1:19:00:00:01")
TV = DiscoveredHost("192.168.100.30", "aa:bb:cc:00:00:03")


def scan(client: TestClient, auth: dict[str, str], scanner: FakeScanner, *hosts: DiscoveredHost):
    scanner.hosts = list(hosts)
    r = client.post("/api/v1/devices/scan", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def by_mac(client: TestClient, auth: dict[str, str]) -> dict[str, dict]:
    return {d["mac"]: d for d in client.get("/api/v1/devices", headers=auth).json()}


def test_first_scan_creates_devices_as_unknown_with_vendor(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    result = scan(client, auth, scanner, GW, PHONE)
    assert (result["found"], result["new"]) == (2, 2) and result["network"] == "192.168.100.0/24"
    devices = by_mac(client, auth)
    assert devices[GW.mac]["vendor"] == "Fabricante Teste"
    assert devices[PHONE.mac]["vendor"] == "MAC privado (aleatório)"
    assert all(d["is_known"] is False and d["online"] for d in devices.values())  # nada presumido


def test_ip_change_hostname_and_history(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, PHONE)
    moved = DiscoveredHost("192.168.100.99", PHONE.mac, "celular.lan")
    scan(client, auth, scanner, moved)
    device = by_mac(client, auth)[PHONE.mac]
    assert device["ip"] == "192.168.100.99" and device["hostname"] == "celular.lan"
    events = client.get(f"/api/v1/devices/{device['id']}/events", headers=auth).json()
    assert {e["event_type"] for e in events} == {"connected", "ip_changed"}
    assert any("192.168.100.20 → 192.168.100.99" in (e["detail"] or "") for e in events)


def test_offline_only_after_consecutive_misses_then_reconnects(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, TV)
    scan(client, auth, scanner, GW)  # 1ª ausência: ainda online (limiar = 2)
    assert by_mac(client, auth)[TV.mac]["online"] is True
    r = scan(client, auth, scanner, GW)  # 2ª ausência
    assert r["disconnected"] == 1 and by_mac(client, auth)[TV.mac]["online"] is False
    r = scan(client, auth, scanner, GW, TV)
    assert r["reconnected"] == 1 and by_mac(client, auth)[TV.mac]["online"] is True
    tv = by_mac(client, auth)[TV.mac]
    kinds = [
        e["event_type"]
        for e in client.get(f"/api/v1/devices/{tv['id']}/events", headers=auth).json()
    ]
    assert kinds == ["connected", "disconnected", "connected"]  # mais recente primeiro


def test_single_missed_scan_resets_when_device_returns(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, TV)
    scan(client, auth, scanner)
    scan(client, auth, scanner, TV)
    scan(client, auth, scanner)  # contador recomeçou: ainda não passou do limiar
    assert by_mac(client, auth)[TV.mac]["online"] is True


def test_edit_device_and_filters(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    dev = by_mac(client, auth)[PHONE.mac]
    r = client.patch(
        f"/api/v1/devices/{dev['id']}",
        json={"custom_name": "  Celular da Ana ", "category": "smartphone", "is_known": True},
        headers=auth,
    )
    assert r.json()["custom_name"] == "Celular da Ana" and r.json()["category"] == "smartphone"
    assert [d["mac"] for d in client.get("/api/v1/devices?known=false", headers=auth).json()] == [
        GW.mac
    ]
    cleared = client.patch(f"/api/v1/devices/{dev['id']}", json={"custom_name": ""}, headers=auth)
    assert cleared.json()["custom_name"] is None and cleared.json()["category"] == "smartphone"
    assert client.patch("/api/v1/devices/999", json={}, headers=auth).status_code == 404
    bad = client.patch(f"/api/v1/devices/{dev['id']}", json={"category": "hacker"}, headers=auth)
    assert bad.status_code == 422


def test_mark_all_known(client: TestClient, auth: dict[str, str], scanner: FakeScanner) -> None:
    scan(client, auth, scanner, GW, PHONE, TV)
    assert client.post("/api/v1/devices/mark-all-known", headers=auth).json() == {"updated": 3}
    assert client.post("/api/v1/devices/mark-all-known", headers=auth).json() == {"updated": 0}


def test_scan_requires_admin_and_viewer_can_read(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner, session_factory
) -> None:
    scan(client, auth, scanner, GW)
    with session_factory() as s:
        s.add(User(username="leitor", password_hash=hash_password("senha-leitor-1"), role="viewer"))
        s.commit()
    token = client.post(
        "/api/v1/auth/login", json={"username": "leitor", "password": "senha-leitor-1"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/devices", headers=h).status_code == 200
    assert client.post("/api/v1/devices/scan", headers=h).status_code == 403
    assert client.post("/api/v1/devices/mark-all-known", headers=h).status_code == 403
    assert client.patch("/api/v1/devices/1", json={"is_known": True}, headers=h).status_code == 403
    assert client.get("/api/v1/devices").status_code == 401


def test_scan_unavailable_returns_503_and_keeps_inventory(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW)
    scanner.unavailable = True
    r = client.post("/api/v1/devices/scan", headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"
    assert by_mac(client, auth)[GW.mac]["online"] is True


def test_scan_refuses_unauthorized_network(
    settings: Settings, client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    client.app.state.settings = settings.model_copy(update={"scan_network": "8.8.8.0/24"})  # type: ignore[attr-defined]
    r = client.post("/api/v1/devices/scan", headers=auth)
    assert r.status_code == 422 and scanner.networks == []


def test_topology_marks_lan_links_as_inferred(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    topo = client.get("/api/v1/topology", headers=auth).json()
    kinds = sorted(n["kind"] for n in topo["nodes"])
    # Sem gateway configurado não se afirma qual aparelho é o gateway: ambos são dispositivos.
    assert kinds == ["device", "device", "gateway", "internet"]
    lan_edges = [e for e in topo["edges"] if e["target"].startswith("device-")]
    assert lan_edges and all(e["confidence"] == "inferred" and e["reason"] for e in lan_edges)
    assert next(e for e in topo["edges"] if e["source"] == "internet")["confidence"] == "inferred"
    assert any("Gateway não configurado" in n for n in topo["notes"])


def test_topology_merges_gateway_device_and_confirms_internet_link(
    client: TestClient,
    auth: dict[str, str],
    scanner: FakeScanner,
    settings: Settings,
    probe: FakeProbe,
) -> None:
    add_target(client, auth, "Gateway", "192.168.100.1", kind="gateway")
    add_target(client, auth, "A", "1.1.1.1")
    cycle(client, settings, probe)
    scan(client, auth, scanner, GW, PHONE)
    topo = client.get("/api/v1/topology", headers=auth).json()
    gateway = next(n for n in topo["nodes"] if n["kind"] == "gateway")
    assert gateway["ip"] == "192.168.100.1" and gateway["device_id"] is not None
    assert (
        sum(1 for n in topo["nodes"] if n["ip"] == "192.168.100.1") == 1
    )  # sem duplicar o gateway
    assert next(e for e in topo["edges"] if e["source"] == "internet")["confidence"] == "confirmed"


def test_topology_gateway_down_is_offline_and_link_not_confirmed(
    client: TestClient,
    auth: dict[str, str],
    settings: Settings,
    probe: FakeProbe,
) -> None:
    add_target(client, auth, "Gateway", "192.168.100.1", kind="gateway")
    add_target(client, auth, "A", "1.1.1.1")
    probe.down = {"192.168.100.1"}
    cycle(client, settings, probe, times=2)
    topo = client.get("/api/v1/topology", headers=auth).json()
    assert next(n for n in topo["nodes"] if n["kind"] == "gateway")["status"] == "offline"
    assert next(e for e in topo["edges"] if e["source"] == "internet")["confidence"] == "inferred"


def test_import_names_from_router_table_keeps_custom_name(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    scan(client, auth, scanner, GW, PHONE)
    devices = by_mac(client, auth)
    client.patch(
        f"/api/v1/devices/{devices[PHONE.mac]['id']}",
        json={"custom_name": "Meu celular"},
        headers=auth,
    )
    text = (
        "iPhone-do-David\t192.168.100.20\tDA:A1:19:00:00:01\n"
        "Outro\t192.168.100.77\t11:22:33:44:55:66\n"
    )
    r = client.post("/api/v1/devices/import-names", json={"text": text}, headers=auth)
    assert r.status_code == 200 and r.json() == {"parsed": 2, "matched": 1, "updated": 1}
    phone = by_mac(client, auth)[PHONE.mac]
    assert phone["hostname"] == "iPhone-do-David" and phone["custom_name"] == "Meu celular"


def test_import_names_requires_admin(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/v1/devices/import-names", json={"text": "x"}).status_code == 401


def test_port_scan_stores_open_ports_and_replaces_closed(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner, port_scanner
) -> None:
    scan(client, auth, scanner, PHONE)
    device_id = by_mac(client, auth)[PHONE.mac]["id"]
    port_scanner.open_ports = [80, 443]
    r = client.post(f"/api/v1/devices/{device_id}/ports/scan", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert [p["port"] for p in body["open_ports"]] == [80, 443] and body["checked"] > 10
    assert body["open_ports"][0]["service"] == "HTTP"
    port_scanner.open_ports = [443]
    client.post(f"/api/v1/devices/{device_id}/ports/scan", headers=auth)
    stored = client.get(f"/api/v1/devices/{device_id}/ports", headers=auth).json()
    assert [p["port"] for p in stored] == [443]
    assert by_mac(client, auth)[PHONE.mac]["ports_scanned_at"] is not None
    assert port_scanner.scanned == [PHONE.ip, PHONE.ip]


def test_port_scan_refuses_ip_outside_authorized_ranges(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner, port_scanner
) -> None:
    scan(client, auth, scanner, DiscoveredHost("192.168.100.20", "da:a1:19:00:00:01"))
    device_id = by_mac(client, auth)["da:a1:19:00:00:01"]["id"]
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        session.execute(update(Device).values(ip="8.8.8.8"))
        session.commit()
    r = client.post(f"/api/v1/devices/{device_id}/ports/scan", headers=auth)
    assert r.status_code == 422 and port_scanner.scanned == []


def test_port_scan_unknown_device_is_404(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/v1/devices/999/ports/scan", headers=auth).status_code == 404
