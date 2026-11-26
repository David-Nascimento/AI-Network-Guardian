"""Regras puras que separam queda de um destino de queda geral da internet.

Sem acesso a banco ou rede: recebe a saúde atual de cada destino e devolve os
incidentes que deveriam estar abertos. Isso torna a lógica fácil de testar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_MIN_EXTERNALS_FOR_OUTAGE = 2  # com um só destino externo não dá para afirmar queda geral


@dataclass(frozen=True, slots=True)
class TargetHealth:
    target_id: int
    name: str
    kind: str  # gateway | external | dns
    down: bool
    consecutive_failures: int = 0
    known: bool = True  # False = ainda sem nenhuma medição deste destino


@dataclass(frozen=True, slots=True)
class Incident:
    key: str
    event_type: str
    severity: str
    target_id: int | None
    message: str
    details: dict[str, object] = field(default_factory=dict)


def _evidence(items: list[TargetHealth]) -> dict[str, object]:
    return {
        "targets": [
            {"id": t.target_id, "name": t.name, "consecutive_failures": t.consecutive_failures}
            for t in items
        ]
    }


def classify(health: list[TargetHealth]) -> list[Incident]:
    gateways = [h for h in health if h.kind == "gateway"]
    externals = [h for h in health if h.kind == "external"]
    dns = [h for h in health if h.kind == "dns"]

    gateway_down = bool(gateways) and all(g.down for g in gateways)
    if gateway_down:
        # Sem gateway, o resto é consequência: um único incidente local.
        return [
            Incident(
                key="gateway_down",
                event_type="gateway_down",
                severity="critical",
                target_id=None,
                message="Gateway local sem resposta: possível problema no roteador ou no Wi-Fi.",
                details=_evidence(gateways),
            )
        ]

    incidents: list[Incident] = []
    external_down = [e for e in externals if e.down]
    # Só afirmamos que a internet funciona se há medições e nenhuma falha nos externos.
    externals_ok = bool(externals) and all(e.known and not e.down for e in externals)
    all_external_down = len(externals) >= _MIN_EXTERNALS_FOR_OUTAGE and len(external_down) == len(
        externals
    )

    if all_external_down:
        scope = "gateway respondendo" if gateways else "gateway não monitorado"
        incidents.append(
            Incident(
                key="internet_down",
                event_type="internet_down",
                severity="critical",
                target_id=None,
                message=(
                    f"Todos os destinos externos falharam ({scope}): possível queda do provedor."
                ),
                details=_evidence(externals),
            )
        )
    else:
        incidents.extend(
            Incident(
                key=f"target_down:{e.target_id}",
                event_type="target_down",
                severity="warning",
                target_id=e.target_id,
                message=f"Destino '{e.name}' indisponível enquanto os demais respondem.",
                details=_evidence([e]),
            )
            for e in external_down
        )
        incidents.extend(
            Incident(
                key=f"dns_down:{d.target_id}",
                event_type="dns_down",
                severity="warning",
                target_id=d.target_id,
                message=(
                    f"Falha de resolução DNS em '{d.name}' com conectividade externa ativa."
                    if externals_ok
                    else f"Falha de resolução DNS em '{d.name}'."
                ),
                details=_evidence([d]),
            )
            for d in dns
            if d.down
        )
    return incidents
