from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.collectors import CollectorUnavailableError, ProbeResult
from app.collectors.arp_collector import DiscoveredHost
from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.database.base import Base
from app.database.session import build_engine, build_session_factory
from app.main import create_app

ADMIN_USER = "admin"
ADMIN_PASSWORD = "senha-forte-123"


class FakeProbe:
    """Sonda controlada pelo teste: define por host se responde, e quanto demora."""

    def __init__(self) -> None:
        self.down: set[str] = set()
        self.unavailable = False
        self.calls: list[str] = []

    def run(self, host: str, *, port: int | None, count: int, timeout: float) -> ProbeResult:
        self.calls.append(host)
        if self.unavailable:
            raise CollectorUnavailableError("sem ping")
        if host in self.down:
            return ProbeResult.from_rtts(count, [])
        return ProbeResult.from_rtts(count, [10.0, 12.0, 11.0, 15.0][:count])


class FakeScanner:
    """Scanner controlado pelo teste: `hosts` é o que a próxima varredura 'enxerga'."""

    def __init__(self) -> None:
        self.hosts: list[DiscoveredHost] = []
        self.unavailable = False
        self.networks: list[str] = []

    def scan(self, network: object) -> list[DiscoveredHost]:
        self.networks.append(str(network))
        if self.unavailable:
            raise CollectorUnavailableError("sem arp")
        return list(self.hosts)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite://",
        scheduler_enabled=False,
        seed_default_targets=False,
        admin_username=ADMIN_USER,
        admin_password=ADMIN_PASSWORD,  # type: ignore[arg-type]
        failure_threshold=2,
        scan_network="192.168.100.0/24",
        offline_after_scans=2,
        reverse_dns=False,
        ping_count=4,
        login_rate_limit=5,
    )


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    eng = build_engine(settings.database_url)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine):  # type: ignore[no-untyped-def]
    return build_session_factory(engine)


@pytest.fixture
def probe() -> FakeProbe:
    return FakeProbe()


class FakePortScanner:
    def __init__(self) -> None:
        self.open_ports: list[int] = []
        self.scanned: list[str] = []

    def scan(self, ip: str) -> list[int]:
        self.scanned.append(ip)
        return list(self.open_ports)


@pytest.fixture
def scanner() -> FakeScanner:
    return FakeScanner()


@pytest.fixture
def port_scanner() -> FakePortScanner:
    return FakePortScanner()


@pytest.fixture
def client(
    settings: Settings,
    engine: Engine,
    probe: FakeProbe,
    scanner: FakeScanner,
    port_scanner: FakePortScanner,
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        engine=engine,
        probes={"icmp": probe, "tcp": probe, "dns": probe},
        scanner=scanner,
        port_scanner=port_scanner,
        oui=OuiDatabase({"F4B520": "Fabricante Teste"}),
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_target(
    client: TestClient,
    auth: dict[str, str],
    name: str,
    host: str,
    *,
    kind: str = "external",
    method: str = "icmp",
    port: int | None = None,
) -> int:
    body = {"name": name, "host": host, "kind": kind, "method": method, "port": port}
    r = client.post("/api/v1/network/targets", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])
