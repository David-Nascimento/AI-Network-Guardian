from __future__ import annotations

import ipaddress
from pathlib import Path

import pytest

from app.collectors import CollectorUnavailableError
from app.collectors.arp_collector import (
    ArpScanner,
    detect_local_network,
    normalize_mac,
    parse_neighbors,
    parse_windows_neighbors,
    validate_scan_network,
)
from app.collectors.oui import (
    PRIVATE_MAC_LABEL,
    OuiDatabase,
    is_locally_administered,
    resolve_oui_path,
)

AUTH = [ipaddress.ip_network("192.168.0.0/16")]

LINUX_NEIGH = """192.168.100.1 dev eth0 lladdr f4:b5:20:48:72:b4 REACHABLE
192.168.100.20 dev eth0 lladdr aa:bb:cc:dd:ee:ff STALE
192.168.100.30 dev eth0  FAILED
192.168.100.31 dev eth0 lladdr 11:22:33:44:55:66 INCOMPLETE
"""
PROC_ARP = """IP address       HW type     Flags       HW address            Mask     Device
192.168.100.1    0x1         0x2         f4:b5:20:48:72:b4     *        eth0
192.168.100.9    0x1         0x0         00:00:00:00:00:00     *        eth0
"""
WINDOWS = """Interface: 192.168.100.24 --- 0x7
  Internet Address      Physical Address      Type
  192.168.100.1         f4-b5-20-48-72-b4     dynamic
  192.168.100.255       ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""
MACOS = """? (192.168.100.1) at f4:b5:20:48:72:b4 on en0 ifscope [ethernet]
? (192.168.100.7) at a:b:c:d:e:f on en0 ifscope [ethernet]
? (192.168.100.8) at (incomplete) on en0 ifscope [ethernet]
"""


def test_parse_linux_ip_neigh_skips_failed_and_incomplete() -> None:
    assert parse_neighbors("Linux", LINUX_NEIGH) == {
        "192.168.100.1": "f4:b5:20:48:72:b4",
        "192.168.100.20": "aa:bb:cc:dd:ee:ff",
    }


def test_parse_proc_arp_skips_incomplete_entries() -> None:
    assert parse_neighbors("Linux", PROC_ARP) == {"192.168.100.1": "f4:b5:20:48:72:b4"}


def test_parse_windows_ignora_multicast_e_broadcast() -> None:
    assert parse_neighbors("Windows", WINDOWS) == {"192.168.100.1": "f4:b5:20:48:72:b4"}


def test_parse_macos_pads_short_octets_and_skips_incomplete() -> None:
    assert parse_neighbors("Darwin", MACOS) == {
        "192.168.100.1": "f4:b5:20:48:72:b4",
        "192.168.100.7": "0a:0b:0c:0d:0e:0f",
    }


def test_normalize_mac() -> None:
    assert normalize_mac("F4-B5-20-48-72-B4") == "f4:b5:20:48:72:b4"


@pytest.mark.parametrize(
    "net", ["8.8.8.0/24", "127.0.0.0/24", "169.254.0.0/16", "10.0.0.0/24", "192.168.0.0/16"]
)
def test_validate_scan_network_rejects(net: str) -> None:
    with pytest.raises(ValueError):
        validate_scan_network(ipaddress.IPv4Network(net), AUTH)


def test_validate_scan_network_accepts_authorized_private() -> None:
    net = ipaddress.IPv4Network("192.168.100.0/24")
    assert validate_scan_network(net, AUTH) == net


def test_detect_local_network_is_a_slash_24_or_none() -> None:
    net = detect_local_network()
    assert net is None or net.prefixlen == 24


def test_scanner_filters_to_network_and_resolves_names(monkeypatch: pytest.MonkeyPatch) -> None:
    output = (
        "192.168.100.5 dev eth0 lladdr aa:bb:cc:00:00:01 REACHABLE\n"
        "10.9.9.9 dev eth0 lladdr aa:bb:cc:00:00:02 REACHABLE\n"
    )
    scanner = ArpScanner(timeout=0.01, workers=2, runner=lambda _cmd: output)
    monkeypatch.setattr(scanner, "_sweep", lambda _n: None)
    monkeypatch.setattr(scanner, "_resolve_names", lambda ips: {ips[0]: "notebook.lan"})
    monkeypatch.setattr("app.collectors.arp_collector.platform.system", lambda: "Linux")
    monkeypatch.setattr("app.collectors.arp_collector.shutil.which", lambda _: "/sbin/ip")
    hosts = scanner.scan(ipaddress.IPv4Network("192.168.100.0/24"))
    assert [(h.ip, h.mac, h.hostname) for h in hosts] == [
        ("192.168.100.5", "aa:bb:cc:00:00:01", "notebook.lan")
    ]


def test_oui_private_mac_detection() -> None:
    assert is_locally_administered("da:a1:19:00:00:01")
    assert not is_locally_administered("f4:b5:20:48:72:b4")
    assert OuiDatabase().lookup("da:a1:19:00:00:01") == PRIVATE_MAC_LABEL


def test_oui_without_file_never_guesses() -> None:
    assert OuiDatabase().lookup("f4:b5:20:48:72:b4") is None
    assert len(OuiDatabase.from_file(None)) == 0
    assert len(OuiDatabase.from_file("/nao/existe.txt")) == 0


def test_oui_loads_nmap_and_ieee_formats(tmp_path: Path) -> None:
    f = tmp_path / "oui.txt"
    f.write_text(
        "# comentário\nF4B520\tFabricante Nmap\n"
        "00-1A-2B   (hex)\t\tFabricante IEEE\n001A2B     (base 16)\t\tFabricante IEEE\n",
        encoding="utf-8",
    )
    db = OuiDatabase.from_file(f)
    assert db.lookup("f4:b5:20:48:72:b4") == "Fabricante Nmap"
    assert db.lookup("00:1a:2b:00:00:01") == "Fabricante IEEE"
    assert db.lookup("00:00:01:00:00:01") is None


WINDOWS_PT = """Interface: 192.168.100.24 --- 0x7
  Endereço IP           Endereço físico       Tipo
  192.168.100.1         f4-b5-20-48-72-b4     dinâmico
  192.168.100.255       ff-ff-ff-ff-ff-ff     estático
  224.0.0.22            01-00-5e-00-00-16     estático
"""


def test_parse_windows_em_portugues_e_com_texto_corrompido() -> None:
    assert parse_neighbors("Windows", WINDOWS_PT) == {"192.168.100.1": "f4:b5:20:48:72:b4"}
    corrupted = WINDOWS_PT.replace("â", "\ufffd").replace("í", "\ufffd")
    assert parse_neighbors("Windows", corrupted) == {"192.168.100.1": "f4:b5:20:48:72:b4"}


def test_resolve_oui_path_tenta_cwd_e_raiz_do_projeto(tmp_path: Path) -> None:
    backend, root = tmp_path / "backend", tmp_path
    backend.mkdir()
    (root / "data").mkdir()
    (root / "data" / "oui.txt").write_text("AABBCC Teste\n")
    roots = [backend, root]
    assert resolve_oui_path("./data/oui.txt", roots) == root / "data" / "oui.txt"
    assert (
        resolve_oui_path(None, roots) == root / "data" / "oui.txt"
    )  # arquivo que acompanha o projeto
    assert resolve_oui_path("nao/existe.txt", roots) is None


WIN_NEIGHBOR = """192.168.100.1 B4-64-15-5C-24-18 Reachable
192.168.100.20 50-F2-65-F3-02-C9 Stale
192.168.100.34 4C-EB-42-D1-51-6E Unreachable
192.168.100.35 4C-EB-42-D1-51-70 Incomplete
192.168.100.27 90-39-5F-16-7C-39 Probe
192.168.100.255 FF-FF-FF-FF-FF-FF Permanent
224.0.0.22 01-00-5E-00-00-16 Permanent
"""


def test_parse_windows_netneighbor_conta_so_presenca_confirmada() -> None:
    assert parse_windows_neighbors(WIN_NEIGHBOR) == {
        "192.168.100.1": "b4:64:15:5c:24:18",
        "192.168.100.27": "90:39:5f:16:7c:39",
    }


def test_parse_linux_strict_descarta_stale() -> None:
    assert parse_neighbors("Linux", LINUX_NEIGH, strict=True) == {
        "192.168.100.1": "f4:b5:20:48:72:b4"
    }


def _windows_scanner(monkeypatch: pytest.MonkeyPatch, runner) -> ArpScanner:  # type: ignore[no-untyped-def]
    scanner = ArpScanner(timeout=0.01, workers=2, runner=runner, reverse_dns=False)
    monkeypatch.setattr(scanner, "_sweep", lambda _n: None)
    monkeypatch.setattr("app.collectors.arp_collector.platform.system", lambda: "Windows")
    return scanner


def test_windows_strict_usa_powershell_e_ignora_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    scanner = _windows_scanner(
        monkeypatch, lambda cmd: WIN_NEIGHBOR if cmd[0] == "powershell" else ""
    )
    hosts = scanner.scan(ipaddress.IPv4Network("192.168.100.0/24"))
    assert [h.ip for h in hosts] == ["192.168.100.1", "192.168.100.27"]


def test_windows_sem_powershell_volta_ao_arp(monkeypatch: pytest.MonkeyPatch) -> None:
    def runner(cmd: list[str]) -> str:
        if cmd[0] == "powershell":
            raise CollectorUnavailableError("sem powershell")
        return WINDOWS

    scanner = _windows_scanner(monkeypatch, runner)
    hosts = scanner.scan(ipaddress.IPv4Network("192.168.100.0/24"))
    assert [h.ip for h in hosts] == ["192.168.100.1"]


def test_nomes_sao_cacheados_entre_varreduras(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_resolve(ip: str, *, timeout: float) -> str | None:
        calls.append(ip)
        return "tv-sala" if ip.endswith(".5") else None

    monkeypatch.setattr("app.collectors.arp_collector.resolve_name", fake_resolve)
    scanner = ArpScanner(timeout=0.01, workers=2, runner=lambda _c: "")
    assert scanner._resolve_names(["192.168.100.5", "192.168.100.6"]) == {
        "192.168.100.5": "tv-sala"
    }
    assert scanner._resolve_names(["192.168.100.5", "192.168.100.6"]) == {
        "192.168.100.5": "tv-sala"
    }
    assert sorted(calls) == ["192.168.100.5", "192.168.100.6"]  # 2ª varredura não reconsultou
