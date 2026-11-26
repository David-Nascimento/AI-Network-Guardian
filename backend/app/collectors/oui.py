"""Fabricante estimado a partir do prefixo (OUI) do MAC.

Não há tabela embutida: prefixos decorados de memória seriam um risco de dado errado. A base é
carregada de um arquivo opcional (`NG_OUI_FILE`), nos formatos Nmap (`AABBCC<TAB>Fabricante`) ou
IEEE (`AA-BB-CC   (hex)   Fabricante`). Sem o arquivo, o fabricante fica desconhecido
(nunca chutado).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from pathlib import Path

log = logging.getLogger(__name__)

PRIVATE_MAC_LABEL = "MAC privado (aleatório)"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED = Path("data/oui.txt")
_NMAP = re.compile(r"^([0-9A-Fa-f]{6})\s+(.+?)\s*$")
_IEEE = re.compile(r"^([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})\s+\(hex\)\s+(.+?)\s*$")


def is_locally_administered(mac: str) -> bool:
    """Bit 'localmente administrado': típico de MAC aleatório de celulares (Wi-Fi privado)."""
    return bool(int(mac[:2], 16) & 0b10)


def resolve_oui_path(configured: str | None, roots: Sequence[Path] | None = None) -> Path | None:
    """Acha o arquivo OUI: o caminho configurado ou, sem ele, o `data/oui.txt` do projeto.

    O caminho relativo é testado também a partir da raiz do repositório, porque o backend costuma
    rodar de `backend/` e um `./data/oui.txt` escrito pensando na raiz não seria encontrado.
    """
    roots = roots if roots is not None else [Path.cwd(), _REPO_ROOT]
    if configured:
        given = Path(configured)
        candidates = [given] if given.is_absolute() else [root / given for root in roots]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        log.warning("NG_OUI_FILE=%s não encontrado; fabricantes ficarão desconhecidos", configured)
        return None
    for root in roots:
        if (root / _BUNDLED).is_file():
            return root / _BUNDLED
    return None


class OuiDatabase:
    def __init__(self, entries: dict[str, str] | None = None) -> None:
        self._entries = entries or {}

    @classmethod
    def from_file(cls, path: str | Path | None) -> OuiDatabase:
        if not path or not Path(path).is_file():
            return cls()
        entries: dict[str, str] = {}
        with Path(path).open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "(base 16)" in line:  # duplicata do IEEE; a linha (hex) já cobre o prefixo
                    continue
                match = _NMAP.match(line) or _IEEE.match(line)
                if match:
                    entries[match.group(1).replace("-", "").upper()] = match.group(2)
        return cls(entries)

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, mac: str) -> str | None:
        if is_locally_administered(mac):
            return PRIVATE_MAC_LABEL
        return self._entries.get(mac.replace(":", "")[:6].upper())
