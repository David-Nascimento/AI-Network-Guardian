"""Ferramentas do agente. Todas SOMENTE LEITURA, em lista fechada, com argumentos validados.

O resultado de uma ferramenta é dado, nunca instrução: nomes de aparelhos, por exemplo, vêm
da rede e podem conter texto arbitrário. Por isso o prompt do sistema manda ignorá-los como
comandos e nenhuma ferramenta altera estado.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.core.exceptions import DomainValidationError
from app.schemas import AlertOut, DeviceEventOut, DeviceOut, EventOut
from app.services import (
    AlertService,
    AnomalyService,
    DeviceService,
    MetricsService,
    NetworkService,
    TopologyService,
)

MAX_RESULT_CHARS = 6000


@dataclass(frozen=True, slots=True)
class Param:
    type: str  # integer | string | boolean
    description: str
    required: bool = False
    minimum: int | None = None
    maximum: int | None = None
    enum: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: Session
    settings: Settings
    oui: OuiDatabase


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    params: dict[str, Param]
    run: Callable[[ToolContext, dict[str, Any]], Any]

    def schema(self) -> dict[str, Any]:
        props: dict[str, Any] = {}
        for key, p in self.params.items():
            spec: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                spec["enum"] = list(p.enum)
            props[key] = spec
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": [k for k, p in self.params.items() if p.required],
                },
            },
        }

    def validate(self, args: dict[str, Any]) -> dict[str, Any]:
        unknown = set(args) - set(self.params)
        if unknown:
            raise DomainValidationError(f"argumentos desconhecidos: {', '.join(sorted(unknown))}")
        clean: dict[str, Any] = {}
        for key, p in self.params.items():
            if key not in args or args[key] is None:
                if p.required:
                    raise DomainValidationError(f"argumento obrigatório ausente: {key}")
                continue
            clean[key] = _coerce(key, p, args[key])
        return clean


def _coerce(key: str, p: Param, value: Any) -> Any:
    if p.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise DomainValidationError(f"{key} deve ser inteiro")
        try:
            number = int(value)
        except ValueError as exc:
            raise DomainValidationError(f"{key} deve ser inteiro") from exc
        if (p.minimum is not None and number < p.minimum) or (
            p.maximum is not None and number > p.maximum
        ):
            raise DomainValidationError(f"{key} fora do intervalo {p.minimum}..{p.maximum}")
        return number
    if p.type == "boolean":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "false"}:
            return str(value).lower() == "true"
        raise DomainValidationError(f"{key} deve ser verdadeiro/falso")
    text = str(value)
    if p.enum and text not in p.enum:
        raise DomainValidationError(f"{key} deve ser um de: {', '.join(p.enum)}")
    return text[:200]


def truncate(data: Any, limit: int = MAX_RESULT_CHARS) -> str:
    """JSON compacto com teto de tamanho; listas perdem itens do fim e avisam que foram cortadas."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) <= limit or not isinstance(data, list):
        return text if len(text) <= limit else text[:limit] + "…[cortado]"
    items = list(data)

    def render() -> str:
        payload = {"items": items, "truncated": True, "total": len(data)}
        return json.dumps(payload, ensure_ascii=False, default=str)

    while items and len(render()) > limit:
        items.pop()
    return render()


def _dump(models: list[Any]) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in models]


def _status(ctx: ToolContext, _: dict[str, Any]) -> Any:
    return NetworkService(ctx.session, ctx.settings).status().model_dump(mode="json")


def _summary(ctx: ToolContext, a: dict[str, Any]) -> Any:
    return (
        MetricsService(ctx.session)
        .summary(hours=a.get("hours", 24), target_id=a.get("target_id"))
        .model_dump(mode="json")
    )


def _devices(ctx: ToolContext, a: dict[str, Any]) -> Any:
    devices = DeviceService(ctx.session, ctx.settings, ctx.oui).list_devices(
        online=a.get("online"), known=a.get("known")
    )
    return _dump([DeviceOut.model_validate(d) for d in devices[: a.get("limit", 50)]])


def _device_events(ctx: ToolContext, a: dict[str, Any]) -> Any:
    svc = DeviceService(ctx.session, ctx.settings, ctx.oui)
    return _dump(
        [DeviceEventOut.model_validate(e) for e in svc.events(a["device_id"], a.get("limit", 20))]
    )


def _network_events(ctx: ToolContext, a: dict[str, Any]) -> Any:
    events = NetworkService(ctx.session, ctx.settings).list_events(
        hours=a.get("hours", 24), active_only=a.get("active_only", False), limit=50
    )
    return _dump([EventOut.model_validate(e) for e in events])


def _alerts(ctx: ToolContext, a: dict[str, Any]) -> Any:
    items = AlertService(ctx.session).list(
        status=a.get("status", "active"), severity=None, limit=a.get("limit", 30)
    )
    return _dump([AlertOut.model_validate(x) for x in items])


def _topology(ctx: ToolContext, _: dict[str, Any]) -> Any:
    topo = TopologyService(ctx.session, ctx.settings, ctx.oui).build()
    return topo.model_dump(mode="json")


def _anomalies(ctx: ToolContext, a: dict[str, Any]) -> Any:
    svc = AnomalyService(ctx.session, ctx.settings, AlertService(ctx.session))
    rows = svc.recent(hours=a.get("hours", 24), limit=30, target_id=None)
    return [
        {
            "target_id": r.target_id,
            "window_start": r.window_start.isoformat(),
            "method": r.method,
            "deviations": r.deviations,
        }
        for r in rows
    ]


_HOURS = Param("integer", "Janela em horas (1 a 720).", minimum=1, maximum=720)

TOOLS: tuple[Tool, ...] = (
    Tool("network_status", "Estado atual da conexão e de cada destino monitorado.", {}, _status),
    Tool(
        "metrics_summary",
        "Latência, jitter, perda e disponibilidade medidos num período.",
        {"hours": _HOURS, "target_id": Param("integer", "Filtra por destino.", minimum=1)},
        _summary,
    ),
    Tool(
        "network_events",
        "Quedas e falhas de rede detectadas (internet, gateway, destino, DNS).",
        {"hours": _HOURS, "active_only": Param("boolean", "Somente as em andamento.")},
        _network_events,
    ),
    Tool(
        "list_devices",
        "Dispositivos descobertos na rede local (online/offline, conhecido ou não).",
        {
            "online": Param("boolean", "Filtra por presença."),
            "known": Param("boolean", "Filtra por já reconhecido pelo dono."),
            "limit": Param("integer", "Máximo de itens.", minimum=1, maximum=100),
        },
        _devices,
    ),
    Tool(
        "device_events",
        "Histórico de um dispositivo (conectou, desconectou, mudou de IP).",
        {
            "device_id": Param("integer", "ID do dispositivo.", required=True, minimum=1),
            "limit": Param("integer", "Máximo de itens.", minimum=1, maximum=50),
        },
        _device_events,
    ),
    Tool(
        "list_alerts",
        "Alertas da central (novos, reconhecidos, resolvidos).",
        {
            "status": Param(
                "string", "Filtro.", enum=("active", "new", "acknowledged", "resolved", "all")
            ),
            "limit": Param("integer", "Máximo de itens.", minimum=1, maximum=100),
        },
        _alerts,
    ),
    Tool(
        "topology",
        "Mapa da rede. Cada ligação é 'confirmed' (medida) ou 'inferred' (presumida).",
        {},
        _topology,
    ),
    Tool(
        "list_anomalies",
        "Janelas em que uma medição fugiu do padrão histórico do destino.",
        {"hours": _HOURS},
        _anomalies,
    ),
)


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...]) -> None:
        self._tools = {t.name: t for t in tools}

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


def build_registry() -> ToolRegistry:
    return ToolRegistry(TOOLS)
