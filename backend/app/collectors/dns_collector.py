"""Sonda de resolução DNS usando o resolvedor do sistema."""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.collectors.types import ProbeResult

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="dns-probe")
_MAX_ATTEMPTS = 3


class DnsProbe:
    def run(self, host: str, *, port: int | None, count: int, timeout: float) -> ProbeResult:
        attempts = max(1, min(count, _MAX_ATTEMPTS))
        rtts: list[float] = []
        last_error: str | None = None
        for _ in range(attempts):
            start = time.perf_counter()
            future = _pool.submit(socket.getaddrinfo, host, None)
            try:
                future.result(timeout=timeout)
                rtts.append((time.perf_counter() - start) * 1000)
            except FutureTimeout:
                last_error = "timeout"
            except OSError as exc:
                last_error = type(exc).__name__
        return ProbeResult.from_rtts(attempts, rtts, error=last_error if not rtts else None)
