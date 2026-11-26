"""Central de alertas: cria sem repetir, resolve quando a condição some, reconhece e configura.

Tipos de alerta são fixos (ver `RULES`) e podem ser ligados/desligados. Um alerta ativo por
`dedupe_key`: a mesma condição não gera dois alertas até ser resolvida. Eventos para o tempo real
ficam em `pending` e são publicados pelo job só depois do commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Alert, AlertRule, NetworkEvent
from app.repositories.alerts import AlertRepository, StatusFilter
from app.schemas import AlertRuleOut, AlertSummary


@dataclass(frozen=True, slots=True)
class RuleInfo:
    label: str
    description: str
    default_enabled: bool


RULES: dict[str, RuleInfo] = {
    "new_device": RuleInfo(
        "Novo dispositivo",
        "Avisa quando um aparelho aparece pela primeira vez e ainda não foi marcado "
        "como conhecido.",
        True,
    ),
    "known_device_offline": RuleInfo(
        "Aparelho conhecido ficou offline",
        "Avisa quando um aparelho marcado como conhecido sai da rede. Pode gerar muitos avisos "
        "com celulares, por isso vem desligado.",
        False,
    ),
    "network_incident": RuleInfo(
        "Queda ou falha de rede",
        "Avisa quando o monitoramento detecta queda de internet, do gateway, "
        "de um destino ou de DNS.",
        True,
    ),
    "anomaly": RuleInfo(
        "Comportamento fora do padrão",
        "Avisa quando o modelo estatístico (Fase 6) vê uma medição incomum. Não é um diagnóstico.",
        True,
    ),
}

_INCIDENT_TITLE = {
    "internet_down": "Internet indisponível",
    "gateway_down": "Gateway sem resposta",
    "target_down": "Destino indisponível",
    "dns_down": "Falha de resolução DNS",
}


class AlertService:
    def __init__(self, session: Session) -> None:
        self._alerts = AlertRepository(session)
        self.pending: list[tuple[str, dict[str, Any]]] = []

    # ---- regras ----------------------------------------------------------
    def seed_rules(self) -> None:
        existing = {r.kind for r in self._alerts.rules()}
        for kind, info in RULES.items():
            if kind not in existing:
                self._alerts.add_rule(AlertRule(kind=kind, enabled=info.default_enabled))

    def rules(self) -> list[AlertRuleOut]:
        stored = {r.kind: r.enabled for r in self._alerts.rules()}
        return [
            AlertRuleOut(
                kind=kind,
                label=info.label,
                description=info.description,
                enabled=stored.get(kind, info.default_enabled),
            )
            for kind, info in RULES.items()
        ]

    def set_rule(self, kind: str, enabled: bool) -> AlertRuleOut:
        if kind not in RULES:
            raise NotFoundError("Tipo de alerta desconhecido")
        rule = self._alerts.rule(kind)
        if rule is None:
            self._alerts.add_rule(AlertRule(kind=kind, enabled=enabled))
        else:
            rule.enabled = enabled
        info = RULES[kind]
        return AlertRuleOut(
            kind=kind, label=info.label, description=info.description, enabled=enabled
        )

    def _enabled(self, kind: str) -> bool:
        rule = self._alerts.rule(kind)
        return rule.enabled if rule is not None else RULES[kind].default_enabled

    # ---- criação e resolução --------------------------------------------
    def raise_alert(
        self,
        *,
        kind: str,
        dedupe_key: str,
        severity: str,
        title: str,
        message: str,
        device_id: int | None = None,
        now: datetime | None = None,
    ) -> Alert | None:
        if not self._enabled(kind) or self._alerts.open_by_key(dedupe_key) is not None:
            return None
        alert = self._alerts.add(
            Alert(
                kind=kind,
                severity=severity,
                title=title[:160],
                message=message,
                dedupe_key=dedupe_key,
                device_id=device_id,
                created_at=now or datetime.now(UTC),
            )
        )
        self.pending.append(
            ("alert.created", {"id": alert.id, "severity": severity, "title": alert.title})
        )
        return alert

    def resolve(self, dedupe_key: str, now: datetime | None = None) -> bool:
        alert = self._alerts.open_by_key(dedupe_key)
        if alert is None:
            return False
        alert.resolved_at = now or datetime.now(UTC)
        self.pending.append(("alert.updated", {"id": alert.id}))
        return True

    def resolve_device(self, device_id: int, kind: str, now: datetime | None = None) -> int:
        alerts = self._alerts.open_for_device(device_id, kind)
        for alert in alerts:
            alert.resolved_at = now or datetime.now(UTC)
            self.pending.append(("alert.updated", {"id": alert.id}))
        return len(alerts)

    def resolve_kind(self, kind: str, now: datetime | None = None) -> int:
        count = 0
        for alert in self._alerts.find(status="active", severity=None, limit=10_000):
            if alert.kind == kind:
                alert.resolved_at = now or datetime.now(UTC)
                self.pending.append(("alert.updated", {"id": alert.id}))
                count += 1
        return count

    def sync_network(self, opened: list[NetworkEvent], closed: list[NetworkEvent]) -> None:
        for event in opened:
            self.raise_alert(
                kind="network_incident",
                dedupe_key=f"net:{event.incident_key}",
                severity=event.severity,
                title=_INCIDENT_TITLE.get(event.event_type, "Incidente de rede"),
                message=event.message,
                now=event.started_at,
            )
        for event in closed:
            self.resolve(f"net:{event.incident_key}", event.ended_at)

    # ---- consulta e ação do usuário -------------------------------------
    def list(self, *, status: StatusFilter, severity: str | None, limit: int) -> list[Alert]:
        return self._alerts.find(status=status, severity=severity, limit=limit)

    def summary(self) -> AlertSummary:
        new, acknowledged, critical = self._alerts.count_active()
        return AlertSummary(new=new, acknowledged=acknowledged, critical_active=critical)

    def acknowledge(self, alert_id: int, user: str) -> Alert:
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise NotFoundError("Alerta não encontrado")
        if alert.acknowledged_at is None:
            alert.acknowledged_at = datetime.now(UTC)
            alert.acknowledged_by = user
        return alert

    def acknowledge_all(self, user: str) -> int:
        return self._alerts.acknowledge_all(user, datetime.now(UTC))
