"""Sondas de latência: ICMP (comando `ping` do SO, sem privilégios) e TCP connect.

O TCP existe porque muitos roteadores não respondem ICMP; medir o tempo de conexão
numa porta aberta (ex.: 53 ou 80 do gateway) evita falsos 100% de perda.
"""

from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
import time

from app.collectors.process import run_command
from app.collectors.types import CollectorUnavailableError, ProbeResult

_RTT = re.compile(r"[=<]\s*([\d.,]+)\s*ms", re.IGNORECASE)


def parse_ping_rtts(output: str) -> list[float]:
    """Extrai RTTs das linhas de resposta (que contêm TTL), ignorando o resumo final."""
    rtts: list[float] = []
    for line in output.splitlines():
        if "ttl" not in line.lower():
            continue
        match = _RTT.search(line)
        if match:
            rtts.append(float(match.group(1).replace(",", ".")))
    return rtts


def build_ping_command(system: str, host: str, count: int, timeout: float) -> list[str]:
    if system == "Windows":
        return ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), host]
    if system == "Darwin":  # -W em ms no macOS
        return ["ping", "-c", str(count), "-W", str(int(timeout * 1000)), "-n", host]
    return ["ping", "-c", str(count), "-W", str(max(1, int(timeout))), "-n", host]


class IcmpProbe:
    def run(self, host: str, *, port: int | None, count: int, timeout: float) -> ProbeResult:
        if shutil.which("ping") is None:
            raise CollectorUnavailableError("comando 'ping' não encontrado no sistema")
        cmd = build_ping_command(platform.system(), host, count, timeout)
        try:
            output = run_command(cmd, count * timeout + 5)
        except subprocess.TimeoutExpired:
            return ProbeResult.from_rtts(count, [], error="timeout")
        return ProbeResult.from_rtts(count, parse_ping_rtts(output))


class TcpProbe:
    def run(self, host: str, *, port: int | None, count: int, timeout: float) -> ProbeResult:
        if port is None:
            raise ValueError("TcpProbe exige porta")
        rtts: list[float] = []
        last_error: str | None = None
        for _ in range(count):
            start = time.perf_counter()
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    rtts.append((time.perf_counter() - start) * 1000)
            except OSError as exc:
                last_error = type(exc).__name__
        return ProbeResult.from_rtts(count, rtts, error=last_error if not rtts else None)
