"""Gestão de destinos, avaliação de conectividade e eventos de queda."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.network_guard import validate_host
from app.models import MonitorTarget, NetworkEvent
from app.repositories import EventRepository, MetricRepository, TargetRepository
from app.schemas import (
    EventOut,
    NetworkStatus,
    TargetCreate,
    TargetOut,
    TargetStatus,
    TargetUpdate,
)
from app.schemas.network import ConnectivityState
from app.services.connectivity import Incident, TargetHealth, classify

_HIGH_LOSS_PCT = 10.0


@dataclass(frozen=True, slots=True)
class Evaluation:
    opened: list[NetworkEvent]
    closed: list[NetworkEvent]


DEFAULT_TARGETS: tuple[tuple[str, str, str, str, int | None], ...] = (
    ("Cloudflare DNS", "1.1.1.1", "external", "icmp", None),
    ("Google DNS", "8.8.8.8", "external", "icmp", None),
    ("Resolução DNS", "cloudflare.com", "dns", "dns", None),
)


class NetworkService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._targets = TargetRepository(session)
        self._metrics = MetricRepository(session)
        self._events = EventRepository(session)
        self._settings = settings

    # ---- destinos -------------------------------------------------------
    def list_targets(self, *, enabled_only: bool = False) -> list[MonitorTarget]:
        return self._targets.list(enabled_only=enabled_only)

    def create_target(self, data: TargetCreate) -> MonitorTarget:
        host = self._validated_host(data.host, data.method)
        if self._targets.get_by_name(data.name):
            raise ConflictError("Já existe um destino com esse nome")
        target = MonitorTarget(
            name=data.name,
            host=host,
            kind=data.kind,
            method=data.method,
            port=data.port,
            enabled=data.enabled,
        )
        try:
            return self._targets.add(target)
        except IntegrityError as exc:  # corrida entre duas requisições
            raise ConflictError("Já existe um destino com esse nome") from exc

    def update_target(self, target_id: int, data: TargetUpdate) -> MonitorTarget:
        target = self._get(target_id)
        if data.name is not None and data.name != target.name:
            if self._targets.get_by_name(data.name):
                raise ConflictError("Já existe um destino com esse nome")
            target.name = data.name
        if data.enabled is not None:
            target.enabled = data.enabled
        return target

    def delete_target(self, target_id: int) -> None:
        self._targets.delete(self._get(target_id))

    def seed_defaults(self) -> int:
        if self._targets.count() > 0:
            return 0
        seeds = list(DEFAULT_TARGETS)
        if self._settings.gateway_host:
            seeds.insert(0, ("Gateway local", self._settings.gateway_host, "gateway", "icmp", None))
        for name, host, kind, method, port in seeds:
            self.create_target(
                TargetCreate(name=name, host=host, kind=kind, method=method, port=port)  # type: ignore[arg-type]
            )
        return len(seeds)

    def _get(self, target_id: int) -> MonitorTarget:
        target = self._targets.get(target_id)
        if target is None:
            raise NotFoundError("Destino não encontrado")
        return target

    def _validated_host(self, host: str, method: str) -> str:
        value = validate_host(host, self._settings.authorized_network_list)
        if method != "dns" and "." not in value and ":" not in value:
            raise DomainValidationError("Informe um IP ou nome de domínio completo")
        return value

    # ---- avaliação de conectividade ------------------------------------
    def evaluate(self) -> Evaluation:
        """Abre/fecha eventos conforme a saúde atual. Devolve o que abriu e o que fechou agora."""
        health = self._health(self._targets.list(enabled_only=True))
        wanted = {i.key: i for i in classify(health)}
        now = datetime.now(UTC)
        opened: list[NetworkEvent] = []
        closed: list[NetworkEvent] = []

        for event in self._events.open_events():
            if event.incident_key in wanted:
                del wanted[event.incident_key]
            else:
                event.ended_at = now
                closed.append(event)
        for incident in wanted.values():
            opened.append(self._events.add(self._to_event(incident, now)))
        return Evaluation(opened, closed)

    def status(self) -> NetworkStatus:
        targets = self._targets.list(enabled_only=True)
        health = {h.target_id: h for h in self._health(targets)}
        rows: list[TargetStatus] = []
        for t in targets:
            last = self._metrics.latest(t.id)
            rows.append(
                TargetStatus(
                    target=TargetOut.model_validate(t),
                    down=health[t.id].down,
                    last_sample_at=last.ts if last else None,
                    latency_avg_ms=last.latency_avg_ms if last else None,
                    packet_loss_pct=last.packet_loss_pct if last else None,
                )
            )
        active = [EventOut.model_validate(e) for e in self._events.open_events()]
        state, summary = self._summarize(rows, active)
        return NetworkStatus(
            state=state,
            summary=summary,
            checked_at=datetime.now(UTC),
            targets=rows,
            active_events=active,
        )

    def list_events(self, *, hours: int, active_only: bool, limit: int) -> list[NetworkEvent]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        return self._events.list(since=since, active_only=active_only, limit=limit)

    # ---- internos -------------------------------------------------------
    def _health(self, targets: list[MonitorTarget]) -> list[TargetHealth]:
        n = self._settings.failure_threshold
        out: list[TargetHealth] = []
        for t in targets:
            recent = self._metrics.last_n(t.id, n)
            failures = 0
            for m in recent:
                if m.success:
                    break
                failures += 1
            out.append(
                TargetHealth(
                    target_id=t.id,
                    name=t.name,
                    kind=t.kind,
                    down=len(recent) == n and failures == n,
                    consecutive_failures=failures,
                    known=bool(recent),
                )
            )
        return out

    @staticmethod
    def _to_event(incident: Incident, now: datetime) -> NetworkEvent:
        return NetworkEvent(
            incident_key=incident.key,
            event_type=incident.event_type,
            severity=incident.severity,
            target_id=incident.target_id,
            message=incident.message,
            details=incident.details,
            started_at=now,
        )

    @staticmethod
    def _summarize(
        rows: list[TargetStatus], active: list[EventOut]
    ) -> tuple[ConnectivityState, str]:
        if not rows or all(r.last_sample_at is None for r in rows):
            return "unknown", "Ainda não há medições. Aguarde o primeiro ciclo de coleta."
        critical = [e for e in active if e.severity == "critical"]
        if critical:
            return "offline", critical[0].message
        if active:
            return "degraded", active[0].message
        lossy = [r for r in rows if (r.packet_loss_pct or 0) >= _HIGH_LOSS_PCT]
        if lossy:
            names = ", ".join(r.target.name for r in lossy)
            return "degraded", f"Perda de pacotes elevada em: {names}."
        return "online", "Todos os destinos monitorados estão respondendo."
