"""Middlewares HTTP: cabeçalhos de segurança e identificador de requisição."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

CallNext = Callable[[Request], Awaitable[Response]]

_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_PERMISSIONS = "camera=(), microphone=(), geolocation=()"


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next: CallNext) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS)
        if request.url.path.startswith("/api/"):
            # A API devolve só JSON/CSV: nada de executar conteúdo nem de guardar dados em cache.
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
            response.headers.setdefault("Cache-Control", "no-store")
        return response
