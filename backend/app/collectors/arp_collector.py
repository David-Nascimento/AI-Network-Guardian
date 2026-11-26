"""Descoberta de dispositivos na LAN autorizada: varredura leve + leitura da tabela ARP do SO.

Sem root nem Scapy: uma tentativa de conexão TCP a cada IP força o SO a resolver o MAC (ARP), e a
tabela de vizinhos é lida com os comandos nativos de cada sistema. Observa só endereços
(IP/MAC/nome); não lê tráfego nem credenciais. O próprio coletor não aparece (sem ARP para si).
"""

from __future__ import annotations

import contextlib
import ipaddress
import platform
import re
import shutil
import socket
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

from app.collectors.names_collector import resolve_name
from app.collectors.process import run_command
from app.collectors.types import CollectorUnavailableError

IPv4Net = ipaddress.IPv4Network
_MAC = r"([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})"
_LINUX_NEIGH = re.compile(rf"^(\d+\.\d+\.\d+\.\d+)\s+.*?lladdr\s+{_MAC}\s+(\S+)")
_PROC_ARP = re.compile(rf"^(\d+\.\d+\.\d+\.\d+)\s+\S+\s+(0x\d+)\s+{_MAC}")
_WINDOWS = re.compile(rf"^\s*(\d+\.\d+\.\d+\.\d+)\s+{_MAC}\s+(\w+)")
_MACOS = re.compile(rf"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+{_MAC}")
_BAD_NEIGH_STATES = {"FAILED", "INCOMPLETE"}
# Em modo estrito só conta quem confirmou presença há pouco (o resto é entrada de cache antiga).
_STALE_NEIGH_STATES = {"STALE"}
_WIN_PRESENT_STATES = {"reachable", "probe", "delay", "permanent"}
_WIN_NEIGHBOR_LINE = re.compile(rf"^\s*(\d+\.\d+\.\d+\.\d+)\s+{_MAC}\s+(\w+)\s*$")
_WIN_NEIGHBOR_CMD = (
    "Get-NetNeighbor -AddressFamily IPv4 | ForEach-Object "
    "{ '{0} {1} {2}' -f $_.IPAddress, $_.LinkLayerAddress, $_.State }"
)
_NAME_TTL_FOUND = 3600.0
_NAME_TTL_MISSING = 300.0
_SWEEP_PORT = 9  # descarte: a porta ser fechada não importa, só o ARP gerado
_MAX_HOSTS = 1024


@dataclass(frozen=True, slots=True)
class DiscoveredHost:
    ip: str
    mac: str
    hostname: str | None = None


class NeighborScanner(Protocol):
    def scan(self, network: IPv4Net) -> list[DiscoveredHost]: ...


def normalize_mac(raw: str) -> str:
    """aa:bb:cc:dd:ee:ff minúsculo, completando zeros (macOS imprime 'a:b:c:d:e:f')."""
    return ":".join(p.zfill(2) for p in re.split(r"[:-]", raw.lower()))


def parse_neighbors(system: str, output: str, *, strict: bool = False) -> dict[str, str]:
    """IP → MAC a partir da saída do comando de vizinhos do SO. Ignora entradas inválidas.

    `strict` descarta entradas STALE (Linux), que são cache antigo de quem já saiu da rede.
    """
    found: dict[str, str] = {}
    for line in output.splitlines():
        ip = mac = None
        if system == "Windows":
            m = _WINDOWS.match(line)
            if m:  # a coluna "Tipo" é localizada ("dynamic"/"dinâmico"); filtramos pelo MAC
                ip, mac = m.group(1), m.group(2)
        elif system == "Darwin":
            m = _MACOS.search(line)
            if m:
                ip, mac = m.group(1), m.group(2)
        else:
            m = _LINUX_NEIGH.match(line)
            bad = _BAD_NEIGH_STATES | (_STALE_NEIGH_STATES if strict else set())
            if m and m.group(3).upper() not in bad:
                ip, mac = m.group(1), m.group(2)
            elif (p := _PROC_ARP.match(line)) and p.group(2) != "0x0":
                ip, mac = p.group(1), p.group(3)
        if ip and mac:
            normalized = normalize_mac(mac)
            first_octet = int(normalized[:2], 16)
            is_multicast = bool(first_octet & 1)  # inclui broadcast e 01:00:5e (entradas estáticas)
            if not is_multicast and normalized != "00:00:00:00:00:00":
                found[ip] = normalized
    return found


def parse_windows_neighbors(output: str) -> dict[str, str]:
    """Saída de `_WIN_NEIGHBOR_CMD`: só entradas com presença confirmada (Reachable/Probe/...)."""
    found: dict[str, str] = {}
    for line in output.splitlines():
        m = _WIN_NEIGHBOR_LINE.match(line)
        if not m or m.group(3).lower() not in _WIN_PRESENT_STATES:
            continue
        mac = normalize_mac(m.group(2))
        if not int(mac[:2], 16) & 1 and mac != "00:00:00:00:00:00":
            found[m.group(1)] = mac
    return found


def validate_scan_network(
    network: IPv4Net, authorized: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
) -> IPv4Net:
    """Só varre redes privadas dentro das faixas autorizadas e de tamanho razoável."""
    if not network.is_private or network.is_loopback or network.is_link_local:
        raise ValueError("Só é permitido varrer redes privadas")
    if not any(network.subnet_of(a) for a in authorized if isinstance(a, IPv4Net)):
        raise ValueError("Rede fora das faixas autorizadas (NG_AUTHORIZED_NETWORKS)")
    if network.num_addresses > _MAX_HOSTS:
        raise ValueError(f"Rede grande demais para varredura (máx. {_MAX_HOSTS} endereços)")
    return network


def detect_local_network() -> IPv4Net | None:
    """/24 da interface de saída padrão. Em container isso é a rede do Docker, não a sua LAN."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))  # TEST-NET-1: UDP connect não envia pacote algum
            ip = sock.getsockname()[0]
    except OSError:
        return None
    return IPv4Net(f"{ip}/24", strict=False)


class ArpScanner:
    def __init__(
        self,
        *,
        timeout: float = 0.4,
        workers: int = 64,
        reverse_dns: bool = True,
        name_timeout: float = 0.8,
        strict: bool = True,
        runner: Callable[[list[str]], str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._workers = workers
        self._reverse_dns = reverse_dns
        self._name_timeout = name_timeout
        self._strict = strict
        self._names: dict[str, tuple[str | None, float]] = {}
        self._run = runner or self._default_runner

    def scan(self, network: IPv4Net) -> list[DiscoveredHost]:
        self._sweep(network)
        table = self._neighbor_table()
        macs = {ip: mac for ip, mac in table.items() if ipaddress.IPv4Address(ip) in network}
        names = self._resolve_names(list(macs)) if self._reverse_dns else {}
        return [DiscoveredHost(ip, mac, names.get(ip)) for ip, mac in sorted(macs.items())]

    # ---- internos -------------------------------------------------------
    def _sweep(self, network: IPv4Net) -> None:
        def poke(ip: str) -> None:
            # Recusado ou sem resposta é o esperado: o ARP já foi resolvido pelo SO.
            with contextlib.suppress(OSError):
                socket.create_connection((ip, _SWEEP_PORT), timeout=self._timeout).close()

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            list(pool.map(poke, (str(h) for h in network.hosts())))

    def _neighbor_table(self) -> dict[str, str]:
        system = platform.system()
        if system == "Windows" and self._strict:
            with contextlib.suppress(CollectorUnavailableError):
                table = parse_windows_neighbors(
                    self._run(["powershell", "-NoProfile", "-Command", _WIN_NEIGHBOR_CMD])
                )
                if table:
                    return table
            # PowerShell indisponível ou sem resultado: volta ao `arp -a` (modo tolerante)
        return parse_neighbors(system, self._read_neighbors(), strict=self._strict)

    def _read_neighbors(self) -> str:
        system = platform.system()
        if system == "Windows":
            return self._run(["arp", "-a"])
        if system == "Darwin":
            return self._run(["arp", "-an"])
        if shutil.which("ip"):
            return self._run(["ip", "-4", "neigh", "show"])
        return self._run(["cat", "/proc/net/arp"])

    def _resolve_names(self, ips: list[str]) -> dict[str, str]:
        """Resolve nomes com cache: quem já tem nome é reconsultado só a cada hora."""
        now = time.monotonic()
        pending = [ip for ip in ips if ip not in self._names or self._names[ip][1] <= now]
        with ThreadPoolExecutor(max_workers=16) as pool:
            resolved = pool.map(lambda ip: resolve_name(ip, timeout=self._name_timeout), pending)
            for ip, name in zip(pending, resolved, strict=True):
                ttl = _NAME_TTL_FOUND if name else _NAME_TTL_MISSING
                self._names[ip] = (name, now + ttl)
        return {ip: name for ip in ips if (name := self._names.get(ip, (None, 0))[0])}

    @staticmethod
    def _default_runner(cmd: list[str]) -> str:
        if shutil.which(cmd[0]) is None:
            raise CollectorUnavailableError(f"comando '{cmd[0]}' não encontrado")
        try:
            return run_command(cmd, 15)
        except subprocess.TimeoutExpired as exc:
            raise CollectorUnavailableError(f"'{cmd[0]}' excedeu o tempo limite") from exc
