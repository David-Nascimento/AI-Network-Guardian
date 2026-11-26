"""Canal em tempo real. O token vai na primeira mensagem (não na URL, que vai para logs)."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.repositories import UserRepository

router = APIRouter(tags=["tempo real"])

_AUTH_TIMEOUT_S = 5
_CLOSE_UNAUTHORIZED = 4401


def _authenticate(ws: WebSocket, token: str) -> bool:
    settings = ws.app.state.settings
    try:
        claims = decode_access_token(token, secret=settings.secret_key.get_secret_value())
    except AuthenticationError:
        return False
    with ws.app.state.session_factory() as session:
        user = UserRepository(session).get_by_username(str(claims["sub"]))
        return user is not None and user.is_active


@router.websocket("/ws")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout=_AUTH_TIMEOUT_S)
        token = message.get("token") if isinstance(message, dict) else None
        if (
            message.get("type") != "auth"
            or not isinstance(token, str)
            or not _authenticate(ws, token)
        ):
            await ws.close(code=_CLOSE_UNAUTHORIZED)
            return
    except (TimeoutError, WebSocketDisconnect, ValueError):
        with contextlib.suppress(RuntimeError):
            await ws.close(code=_CLOSE_UNAUTHORIZED)
        return

    bus = ws.app.state.bus
    queue = bus.subscribe()
    await ws.send_json({"type": "ready", "data": {}, "ts": None})

    async def pump() -> None:
        while True:
            event = await queue.get()
            await ws.send_json(event.as_json())

    sender = asyncio.create_task(pump())
    try:
        while True:  # lê para detectar o fechamento do cliente
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        bus.unsubscribe(queue)
