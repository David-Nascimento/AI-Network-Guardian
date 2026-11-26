"""Importa nomes de aparelhos a partir de texto copiado do painel do roteador (tabela DHCP).

Cada roteador usa um formato; por isso o parser é tolerante: em cada linha procura um MAC e/ou um
IP e escolhe como nome o primeiro campo textual que não seja estado, tempo ou tipo de conexão.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.collectors.arp_collector import normalize_mac

_MAC = re.compile(r"\b[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}\b")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SEPARATORS = re.compile(r"\t|\s{2,}|[,;|]")
_NOT_A_NAME = re.compile(
    r"^(?:dynamic|static|dhcp|online|offline|active|ativo|wireless|wifi|wi-fi|wlan|lan|ethernet|"
    r"[0-9.]+ ?g(?:hz)?|\d+[dhms]?|\d{1,2}:\d{2}(?::\d{2})?|n/?a|-+|\*|unknown|"
    r"permanente|permanent|sim|n[aã]o|yes|no)$",
    re.IGNORECASE,
)
_MAX_NAME = 80


@dataclass(frozen=True)
class RouterEntry:
    mac: str | None
    ip: str | None
    name: str


def _candidate_name(line: str) -> str | None:
    cleaned = _MAC.sub("\t", line)
    cleaned = _IP.sub("\t", cleaned)
    parts = [p.strip() for p in _SEPARATORS.split(cleaned)]
    if len([p for p in parts if p]) <= 1:  # linha separada só por espaços simples
        parts = cleaned.split()
    for part in parts:
        if not part or _NOT_A_NAME.match(part) or not any(c.isalpha() for c in part):
            continue
        return "".join(ch for ch in part if ch.isprintable()).strip()[:_MAX_NAME] or None
    return None


def parse_router_table(text: str) -> list[RouterEntry]:
    entries: list[RouterEntry] = []
    for line in text.splitlines():
        mac_match = _MAC.search(line)
        ip_match = _IP.search(line)
        if not mac_match and not ip_match:
            continue
        name = _candidate_name(line)
        if name is None:
            continue
        mac = normalize_mac(mac_match.group(0)) if mac_match else None
        entries.append(RouterEntry(mac, ip_match.group(0) if ip_match else None, name))
    return entries
