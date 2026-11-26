"""Barramento de eventos em memória: jobs (threads) publicam, conexões WebSocket (asyncio) consomem.

`publish` pode ser chamado de qualquer thread. Sem loop anexado ou sem assinantes, é um no-op,
então jobs e testes não dependem de haver um cliente conectado. Se um cliente fica lento e sua
fila enche, eventos são descartados para ele; o frontend também faz polling como reserva.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_QUEUE_SIZE = 100


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    data: dict[str, Any]
    ts: str

    def as_json(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data, "ts": self.ts}


class EventBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._subscribers:
            return
        event = Event(event_type, data or {}, datetime.now(UTC).isoformat())
        loop.call_soon_threadsafe(self._dispatch, event)

    def _dispatch(self, event: Event) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue  # cliente lento: perde o evento e se atualiza no próximo ou no polling
