"""Descoberta automática de nomes de dispositivos, sem dependências externas.

Ordem de tentativa (a primeira que responder vence):
1. DNS reverso (PTR) do resolvedor do SO — funciona quando o roteador registra os nomes do DHCP;
2. mDNS unicast (UDP 5353) — respondido por Apple, Android, impressoras, Chromecast, etc.;
3. NetBIOS node status (UDP 137) — respondido por PCs Windows, NAS e impressoras.

Nenhum aparelho é obrigado a responder: a falta de nome é normal (ex.: celulares com MAC privado).
Nomes são dado informativo e podem ser trocados pelo usuário; nada aqui afirma identidade.
"""

from __future__ import annotations

import socket
import struct

_MDNS_PORT = 5353
_NBNS_PORT = 137
_MAX_NAME = 80
_DNS_HEADER = 12
_COMPRESSION = 0xC0
_MAX_POINTER_JUMPS = 10
_NB_NAME_ENTRY = 18
_NB_GROUP_FLAG = 0x8000
_NB_WORKSTATION = 0x00
_TYPE_PTR = 12


def clean_name(raw: str) -> str | None:
    """Normaliza o nome: sem sufixo .local, sem controle, até 80 caracteres."""
    name = raw.strip().rstrip(".")
    for suffix in (".local", ".lan", ".home", ".localdomain"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:_MAX_NAME] or None


# ---- mDNS -----------------------------------------------------------------
def build_mdns_ptr_query(ip: str, txid: int = 0) -> bytes:
    labels = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in labels.split(".")) + b"\x00"
    header = struct.pack(">HHHHHH", txid, 0, 1, 0, 0, 0)
    return (
        header + qname + struct.pack(">HH", _TYPE_PTR, 0x8001)
    )  # PTR, classe IN + "responda unicast"


def _read_name(data: bytes, offset: int) -> tuple[str, int]:
    parts: list[str] = []
    end = -1
    jumps = 0
    while True:
        if offset >= len(data):
            raise ValueError("nome truncado")
        length = data[offset]
        if length & _COMPRESSION == _COMPRESSION:
            if offset + 1 >= len(data) or jumps >= _MAX_POINTER_JUMPS:
                raise ValueError("ponteiro inválido")
            if end < 0:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumps += 1
            continue
        if length == 0:
            return ".".join(parts), (end if end >= 0 else offset + 1)
        offset += 1
        parts.append(data[offset : offset + length].decode("utf-8", errors="replace"))
        offset += length


def parse_mdns_ptr(data: bytes) -> str | None:
    """Devolve o primeiro nome PTR da resposta, ou None se inválida/sem resposta."""
    try:
        if len(data) < _DNS_HEADER:
            return None
        _, flags, qd, an, _, _ = struct.unpack(">HHHHHH", data[:_DNS_HEADER])
        if not flags & 0x8000 or an == 0:
            return None
        offset = _DNS_HEADER
        for _ in range(qd):
            _, offset = _read_name(data, offset)
            offset += 4
        for _ in range(an):
            _, offset = _read_name(data, offset)
            rtype, _, _, rdlen = struct.unpack(">HHIH", data[offset : offset + 10])
            offset += 10
            if rtype == _TYPE_PTR:
                target, _ = _read_name(data, offset)
                return clean_name(target)
            offset += rdlen
    except (ValueError, struct.error):
        return None
    return None


# ---- NetBIOS --------------------------------------------------------------
def build_nbns_query(txid: int = 0) -> bytes:
    encoded = b"CK" + b"A" * 30  # "*" codificado em first-level
    header = struct.pack(">HHHHHH", txid, 0, 1, 0, 0, 0)
    return header + b"\x20" + encoded + b"\x00" + struct.pack(">HH", 0x0021, 1)


def parse_nbns(data: bytes) -> str | None:
    """Nome de estação (sufixo 0x00, não de grupo) da resposta node status."""
    try:
        offset = _DNS_HEADER
        _, offset = _read_name(data, offset)
        offset += 10  # tipo, classe, ttl, rdlength
        count = data[offset]
        offset += 1
        for _ in range(count):
            entry = data[offset : offset + _NB_NAME_ENTRY]
            if len(entry) < _NB_NAME_ENTRY:
                return None
            flags = struct.unpack(">H", entry[16:18])[0]
            if entry[15] == _NB_WORKSTATION and not flags & _NB_GROUP_FLAG:
                return clean_name(entry[:15].decode("ascii", errors="replace"))
            offset += _NB_NAME_ENTRY
    except (ValueError, IndexError, struct.error):
        return None
    return None


# ---- consulta de rede -----------------------------------------------------
def _udp_query(ip: str, port: int, payload: bytes, timeout: float) -> bytes | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(payload, (ip, port))
            data, source = sock.recvfrom(2048)
        except OSError:
            return None
    return data if source[0] == ip else None


def resolve_name(ip: str, *, timeout: float = 0.8, reverse_dns: bool = True) -> str | None:
    if reverse_dns:
        try:
            name = clean_name(socket.gethostbyaddr(ip)[0])
        except OSError:
            name = None
        if name and name != ip:
            return name
    response = _udp_query(ip, _MDNS_PORT, build_mdns_ptr_query(ip), timeout)
    if response and (name := parse_mdns_ptr(response)):
        return name
    response = _udp_query(ip, _NBNS_PORT, build_nbns_query(), timeout)
    if response:
        return parse_nbns(response)
    return None
