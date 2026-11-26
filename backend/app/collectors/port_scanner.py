"""Varredura TCP de portas comuns em um dispositivo da rede local autorizada.

Apenas conexão TCP (connect) em uma lista fixa e curta de portas; não coleta banners nem tenta
autenticar. Porta aberta não é vulnerabilidade: indica um serviço que o aparelho oferece.
Os nomes são rótulos convencionais da porta, não garantem qual software está respondendo.
"""

from __future__ import annotations

import contextlib
import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

COMMON_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    53: "DNS",
    80: "HTTP",
    139: "NetBIOS",
    443: "HTTPS",
    445: "SMB (compartilhamento Windows)",
    554: "RTSP (câmeras/streaming)",
    631: "IPP (impressão)",
    1883: "MQTT (IoT)",
    3389: "Área de trabalho remota (RDP)",
    5000: "UPnP / painel web comum",
    5900: "VNC",
    7000: "AirPlay",
    8008: "Chromecast / HTTP alternativo",
    8009: "Chromecast",
    8080: "HTTP alternativo",
    8443: "HTTPS alternativo",
    9100: "Impressão RAW (JetDirect)",
}


class PortScannerProtocol(Protocol):
    def scan(self, ip: str) -> list[int]: ...


class TcpPortScanner:
    def __init__(self, *, timeout: float = 0.6, workers: int = 16) -> None:
        self._timeout = timeout
        self._workers = workers

    def scan(self, ip: str) -> list[int]:
        def check(port: int) -> int | None:
            with contextlib.suppress(OSError):
                socket.create_connection((ip, port), timeout=self._timeout).close()
                return port
            return None

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            return sorted(p for p in pool.map(check, COMMON_PORTS) if p is not None)
