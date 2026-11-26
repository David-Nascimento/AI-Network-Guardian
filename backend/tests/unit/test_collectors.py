from __future__ import annotations

import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.collectors import CollectorUnavailableError, ProbeResult
from app.collectors import ping_collector as pc
from app.collectors.dns_collector import DnsProbe
from app.collectors.ping_collector import IcmpProbe, TcpProbe, build_ping_command, parse_ping_rtts
from app.collectors.process import run_command

LINUX = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=4.12 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=57 time=5.50 ms
--- 1.1.1.1 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 4.120/4.810/5.500/0.690 ms
"""
WINDOWS_PT = """Disparando 8.8.8.8 com 32 bytes de dados:
Resposta de 8.8.8.8: bytes=32 tempo=45ms TTL=115
Resposta de 8.8.8.8: bytes=32 tempo<1ms TTL=115
Esgotado o tempo limite do pedido.
Estatísticas do Ping para 8.8.8.8:
    Mínimo = 1ms, Máximo = 45ms, Média = 23ms
"""


def test_parse_linux_ignores_summary() -> None:
    assert parse_ping_rtts(LINUX) == [4.12, 5.5]


def test_parse_windows_pt_ignores_summary_and_timeouts() -> None:
    assert parse_ping_rtts(WINDOWS_PT) == [45.0, 1.0]


def test_parse_empty() -> None:
    assert parse_ping_rtts("Request timed out") == []


def test_build_command_per_platform() -> None:
    assert build_ping_command("Linux", "h", 4, 2.0) == ["ping", "-c", "4", "-W", "2", "-n", "h"]
    assert build_ping_command("Darwin", "h", 4, 2.0)[3:5] == ["-W", "2000"]
    assert build_ping_command("Windows", "h", 4, 2.0) == ["ping", "-n", "4", "-w", "2000", "h"]


def test_probe_result_stats_and_loss() -> None:
    r = ProbeResult.from_rtts(4, [10.0, 20.0, 15.0])
    assert (r.received, r.latency_min_ms, r.latency_avg_ms, r.latency_max_ms) == (
        3,
        10.0,
        15.0,
        20.0,
    )
    assert r.jitter_ms == 7.5 and r.packet_loss_pct == 25.0 and r.success


def test_probe_result_total_loss_and_single_sample() -> None:
    dead = ProbeResult.from_rtts(4, [])
    assert not dead.success and dead.packet_loss_pct == 100.0 and dead.latency_avg_ms is None
    assert ProbeResult.from_rtts(1, [5.0]).jitter_ms is None


def test_icmp_unavailable_when_no_ping_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pc.shutil, "which", lambda _: None)
    with pytest.raises(CollectorUnavailableError):
        IcmpProbe().run("1.1.1.1", port=None, count=2, timeout=1)


def test_icmp_runs_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pc.shutil, "which", lambda _: "/bin/ping")
    monkeypatch.setattr(pc.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=LINUX))
    r = IcmpProbe().run("1.1.1.1", port=None, count=2, timeout=1)
    assert r.received == 2 and r.packet_loss_pct == 0.0


def test_icmp_timeout_is_a_failure_not_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired("ping", 1)

    monkeypatch.setattr(pc.shutil, "which", lambda _: "/bin/ping")
    monkeypatch.setattr(pc.subprocess, "run", boom)
    r = IcmpProbe().run("1.1.1.1", port=None, count=2, timeout=1)
    assert not r.success and r.error == "timeout"


def test_tcp_probe_open_and_closed_port() -> None:
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen()
        port = srv.getsockname()[1]
        ok = TcpProbe().run("127.0.0.1", port=port, count=2, timeout=1)
    assert ok.received == 2 and ok.latency_avg_ms is not None
    closed = TcpProbe().run("127.0.0.1", port=port, count=1, timeout=0.5)
    assert not closed.success and closed.error is not None


def test_tcp_probe_requires_port() -> None:
    with pytest.raises(ValueError):
        TcpProbe().run("127.0.0.1", port=None, count=1, timeout=1)


def test_dns_probe_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    assert DnsProbe().run("localhost", port=None, count=1, timeout=2).success

    def fail(*_a: object, **_k: object) -> None:
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    r = DnsProbe().run("inexistente.invalid", port=None, count=2, timeout=2)
    assert not r.success and r.sent == 2 and r.error == "gaierror"


def test_run_command_tolera_saida_fora_do_utf8() -> None:
    """Regressão: no Windows o ping escreve em cp850/cp1252; UTF-8 estrito derrubava a sonda."""
    code = "import sys; sys.stdout.buffer.write(b'Resposta de 1.1.1.1: tempo=12ms TTL=57 \\xa1')"
    output = run_command([sys.executable, "-c", code], timeout=10)
    assert parse_ping_rtts(output) == [12.0]
