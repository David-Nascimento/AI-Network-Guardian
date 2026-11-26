from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from app.collectors.arp_collector import DiscoveredHost
from app.core.config import Settings
from app.services.report_service import csv_safe
from tests.conftest import FakeProbe, FakeScanner, add_target
from tests.integration.test_api import cycle
from tests.integration.test_devices import GW, PHONE, scan

API = "/api/v1"


def rows_of(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.removeprefix("﻿")), delimiter=";"))


def test_summary_aggregates_real_data(
    client: TestClient,
    auth: dict[str, str],
    settings: Settings,
    probe: FakeProbe,
    scanner: FakeScanner,
) -> None:
    add_target(client, auth, "Roteador", "192.168.100.1", kind="gateway")
    add_target(client, auth, "Cloudflare", "1.1.1.1")
    cycle(client, settings, probe, times=2)
    probe.down = {"1.1.1.1", "192.168.100.1"}
    cycle(client, settings, probe, times=3)
    scan(client, auth, scanner, GW, PHONE)

    r = client.get(f"{API}/reports/summary", params={"hours": 24}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["samples"] >= 10 and {t["name"] for t in body["targets"]} >= {"Cloudflare"}
    assert body["incidents"]["count"] >= 1 and body["incidents"]["downtime_seconds"] >= 0
    assert body["devices"] == {
        "total": 2,
        "online": 2,
        "known": 0,
        "unknown": 2,
        "first_seen_in_period": 2,
    }
    assert body["alerts"]["created"] >= 2 and "new_device" in body["alerts"]["by_kind"]
    assert any("nada é estimado" in n for n in body["notes"])


def test_summary_validates_and_requires_auth(client: TestClient, auth: dict[str, str]) -> None:
    assert (
        client.get(f"{API}/reports/summary", params={"hours": 0}, headers=auth).status_code == 422
    )
    assert client.get(f"{API}/reports/summary").status_code == 401
    assert client.get(f"{API}/reports/export?kind=metrics").status_code == 401


def test_csv_exports_have_headers_and_content_disposition(
    client: TestClient,
    auth: dict[str, str],
    settings: Settings,
    probe: FakeProbe,
    scanner: FakeScanner,
) -> None:
    add_target(client, auth, "Cloudflare", "1.1.1.1")
    cycle(client, settings, probe, times=2)
    scan(client, auth, scanner, GW)
    for kind, first in [
        ("metrics", "ts_utc"),
        ("events", "inicio_utc"),
        ("devices", "ip"),
        ("alerts", "criado_utc"),
    ]:
        r = client.get(f"{API}/reports/export", params={"kind": kind}, headers=auth)
        assert r.status_code == 200, (kind, r.text)
        assert r.headers["content-type"].startswith("text/csv")
        assert f"guardian-{kind}-" in r.headers["content-disposition"]
        assert rows_of(r.text)[0][0] == first
    devices = rows_of(client.get(f"{API}/reports/export?kind=devices", headers=auth).text)
    assert devices[1][0] == "192.168.100.1" and devices[1][6] == "não"  # desconhecido ≠ malicioso
    assert client.get(f"{API}/reports/export?kind=segredos", headers=auth).status_code == 422


def test_csv_blocks_formula_injection_from_device_names(
    client: TestClient, auth: dict[str, str], scanner: FakeScanner
) -> None:
    evil = DiscoveredHost("192.168.100.77", "aa:bb:cc:00:00:77", '=HYPERLINK("http://x")')
    scan(client, auth, scanner, evil)
    text = client.get(f"{API}/reports/export?kind=devices", headers=auth).text
    assert "'=HYPERLINK" in text and ",=HYPERLINK" not in text
    assert csv_safe("+1") == "'+1" and csv_safe("normal") == "normal" and csv_safe(None) == ""


def test_security_headers_on_api_and_health(client: TestClient, auth: dict[str, str]) -> None:
    api = client.get(f"{API}/alerts", headers=auth)
    assert api.headers["x-content-type-options"] == "nosniff"
    assert api.headers["x-frame-options"] == "DENY"
    assert api.headers["referrer-policy"] == "no-referrer"
    assert api.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in api.headers["content-security-policy"]
    health = client.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in health.headers
