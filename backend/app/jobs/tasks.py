"""Tarefas agendadas: ciclo de coleta e retenção de dados."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.collectors import CollectorUnavailableError, Probe, ProbeResult
from app.collectors.arp_collector import (
    NeighborScanner,
    detect_local_network,
    validate_scan_network,
)
from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.core.exceptions import AppError, DomainValidationError, ServiceUnavailableError
from app.schemas import ScanResult
from app.services import (
    AlertService,
    AnomalyService,
    DeviceService,
    MetricsService,
    NetworkService,
)
from app.websocket import EventBus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TargetSpec:
    """Cópia imutável do destino, segura para usar em threads fora da sessão."""

    id: int
    name: str
    host: str
    method: str
    port: int | None


def run_collection_cycle(
    session_factory: sessionmaker[Session],
    settings: Settings,
    probes: Mapping[str, Probe],
    bus: EventBus | None = None,
) -> int:
    """Mede todos os destinos ativos em paralelo, persiste e reavalia a conectividade.

    Devolve quantas medições foram gravadas. Sondas indisponíveis (ex.: sem `ping`)
    são ignoradas: não representam falha de rede e não devem abrir incidentes.
    """
    with session_factory() as session:
        specs = [
            TargetSpec(t.id, t.name, t.host, t.method, t.port)
            for t in NetworkService(session, settings).list_targets(enabled_only=True)
        ]
    if not specs:
        return 0

    def measure(spec: TargetSpec) -> ProbeResult | None:
        try:
            return probes[spec.method].run(
                spec.host,
                port=spec.port,
                count=settings.ping_count,
                timeout=settings.probe_timeout_seconds,
            )
        except CollectorUnavailableError as exc:
            logger.warning("coletor indisponível", extra={"target": spec.name, "reason": str(exc)})
        except Exception:
            logger.exception("falha inesperada na sonda", extra={"target": spec.name})
        return None

    with ThreadPoolExecutor(max_workers=min(8, len(specs))) as pool:
        results = list(pool.map(measure, specs))

    recorded = 0
    with session_factory() as session:
        metrics = MetricsService(session)
        for spec, result in zip(specs, results, strict=True):
            if result is not None:
                metrics.record(spec.id, result)
                recorded += 1
        evaluation = NetworkService(session, settings).evaluate()
        alerts = AlertService(session)
        alerts.sync_network(evaluation.opened, evaluation.closed)
        session.commit()
        pending = alerts.pending
    _publish(bus, [("network.updated", {"recorded": recorded}), *pending])
    return recorded


def _publish(bus: EventBus | None, events: list[tuple[str, dict[str, Any]]]) -> None:
    if bus is None:
        return
    for event_type, data in events:
        bus.publish(event_type, data)


def run_anomaly_scan(
    session_factory: sessionmaker[Session], settings: Settings, bus: EventBus | None = None
) -> None:
    """Falhas aqui não derrubam o agendador: só registram no log."""
    try:
        with session_factory() as session:
            alerts = AlertService(session)
            events = AnomalyService(session, settings, alerts).scan()
            session.commit()
        _publish(bus, events)
    except Exception:
        logger.exception("anomaly_scan_failed")


def run_retention(session_factory: sessionmaker[Session], settings: Settings) -> int:
    with session_factory() as session:
        removed = MetricsService(session).purge(settings.retention_days)
        session.commit()
    logger.info("retenção aplicada", extra={"removed": removed, "days": settings.retention_days})
    return removed


def resolve_scan_network(settings: Settings) -> ipaddress.IPv4Network:
    """Rede a varrer: NG_SCAN_NETWORK, ou o /24 da interface padrão. Sempre validada."""
    try:
        network = (
            ipaddress.IPv4Network(settings.scan_network, strict=False)
            if settings.scan_network
            else detect_local_network()
        )
        if network is None:
            raise ValueError("Não foi possível detectar a rede local; defina NG_SCAN_NETWORK")
        return validate_scan_network(network, settings.authorized_network_list)
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc


def run_device_scan(
    session_factory: sessionmaker[Session],
    settings: Settings,
    scanner: NeighborScanner,
    oui: OuiDatabase,
    bus: EventBus | None = None,
) -> ScanResult:
    """Varre a LAN autorizada e reconcilia o inventário. Usada pelo agendador e pela API."""
    network = resolve_scan_network(settings)
    try:
        hosts = scanner.scan(network)
    except CollectorUnavailableError as exc:
        raise ServiceUnavailableError(f"Varredura indisponível: {exc}") from exc
    with session_factory() as session:
        service = DeviceService(session, settings, oui)
        result = service.apply_scan(str(network), hosts)
        session.commit()
        events = service.drain_events()
    _publish(bus, [*events, ("devices.updated", result.model_dump(mode="json"))])
    return result


def run_scheduled_device_scan(
    session_factory: sessionmaker[Session],
    settings: Settings,
    scanner: NeighborScanner,
    oui: OuiDatabase,
    bus: EventBus | None = None,
) -> None:
    try:
        result = run_device_scan(session_factory, settings, scanner, oui, bus)
    except AppError as exc:
        logger.warning("varredura ignorada", extra={"reason": exc.message})
        return
    logger.info(
        "varredura concluída",
        extra={"found": result.found, "new": result.new, "disconnected": result.disconnected},
    )
