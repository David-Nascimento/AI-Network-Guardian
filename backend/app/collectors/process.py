"""Execução de comandos do SO para os coletores."""

from __future__ import annotations

import subprocess


def run_command(cmd: list[str], timeout: float) -> str:
    """Roda o comando e devolve a saída padrão como texto.

    A saída é decodificada com `errors="replace"`: no Windows, `ping` e `arp` escrevem na
    página de código OEM do console (cp850/cp1252), não em UTF-8, e acentos do idioma do SO
    quebrariam a decodificação estrita. Os dados que interessam (TTL, ms, IP, MAC) são ASCII.
    Propaga `subprocess.TimeoutExpired`.
    """
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return proc.stdout or ""
