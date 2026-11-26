"""Relatório do período e exportações CSV. Só agrega dados já medidos; não estima nada."""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.core.exceptions import DomainValidationError
from app.schemas import AlertOut, DeviceOut, EventOut
from app.schemas.report import (
    AlertReport,
    DeviceReport,
    IncidentReport,
    ReportSummary,
    TargetReport,
)
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyService
from app.services.device_service import DeviceService
from app.services.metrics_service import MetricsService
from app.services.network_service import NetworkService

ExportKind = Literal["metrics", "events", "devices", "alerts"]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_MAX_ROWS = 5000
_MAX_HOURS = 720


def csv_safe(value: object) -> str:
    """Neutraliza fórmulas de planilha: nomes de aparelhos vêm da rede e não são confiáveis."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def to_csv(header: list[str], rows: list[list[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(c) for c in row])
    return out.getvalue()


class ReportService:
    def __init__(self, session: Session, settings: Settings, oui: OuiDatabase) -> None:
        self._settings = settings
        self._network = NetworkService(session, settings)
        self._metrics = MetricsService(session)
        self._devices = DeviceService(session, settings, oui)
        self._alerts = AlertService(session)
        self._anomalies = AnomalyService(session, settings, self._alerts)

    def summary(self, hours: int) -> ReportSummary:
        _check_hours(hours)
        now = datetime.now(UTC)
        since = now - timedelta(hours=hours)
        overall = self._metrics.summary(hours=hours, target_id=None)

        targets = []
        for t in self._network.list_targets(enabled_only=True):
            s = self._metrics.summary(hours=hours, target_id=t.id)
            targets.append(
                TargetReport(
                    target_id=t.id,
                    name=t.name,
                    availability_pct=s.availability_pct,
                    latency_avg_ms=s.latency_avg_ms,
                    packet_loss_avg_pct=s.packet_loss_avg_pct,
                    samples=s.samples,
                )
            )

        events = self._network.list_events(hours=hours, active_only=False, limit=500)
        downtime = 0
        for e in events:
            start = max(_aware(e.started_at), since)
            end = _aware(e.ended_at) if e.ended_at else now
            downtime += max(0, int((end - start).total_seconds()))

        devices = self._devices.list_devices(online=None, known=None)
        alerts = self._alerts.list(status="all", severity=None, limit=500)
        in_period = [a for a in alerts if _aware(a.created_at) >= since]

        return ReportSummary(
            generated_at=now,
            since=since,
            until=now,
            hours=hours,
            availability_pct=overall.availability_pct,
            latency_avg_ms=overall.latency_avg_ms,
            latency_max_ms=overall.latency_max_ms,
            jitter_avg_ms=overall.jitter_avg_ms,
            packet_loss_avg_pct=overall.packet_loss_avg_pct,
            samples=overall.samples,
            targets=targets,
            incidents=IncidentReport(
                count=len(events),
                downtime_seconds=downtime,
                by_type=dict(Counter(e.event_type for e in events)),
            ),
            devices=DeviceReport(
                total=len(devices),
                online=sum(d.online for d in devices),
                known=sum(d.is_known for d in devices),
                unknown=sum(not d.is_known for d in devices),
                first_seen_in_period=sum(_aware(d.first_seen) >= since for d in devices),
            ),
            alerts=AlertReport(
                created=len(in_period),
                by_kind=dict(Counter(a.kind for a in in_period)),
                still_active=sum(a.resolved_at is None for a in in_period),
            ),
            anomalies=len(self._anomalies.recent(hours, 500, None)),
            notes=[
                "Valores medidos pelos destinos monitorados; nada é estimado.",
                "'Desconhecido' significa apenas que o dono ainda não reconheceu o aparelho.",
                "Inventário de dispositivos é o estado atual, não o do início do período.",
            ],
        )

    def export(self, kind: ExportKind, hours: int) -> tuple[str, str]:
        """Retorna (nome_do_arquivo, conteúdo_csv)."""
        _check_hours(hours)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        name = f"guardian-{kind}-{stamp}.csv"
        if kind == "metrics":
            names = {t.id: t.name for t in self._network.list_targets()}
            pts = self._metrics.history(hours=hours, target_id=None, bucket_minutes=5)[:_MAX_ROWS]
            return name, to_csv(
                [
                    "ts_utc",
                    "destino",
                    "latencia_media_ms",
                    "latencia_max_ms",
                    "jitter_ms",
                    "perda_pct",
                    "amostras",
                ],
                [
                    [
                        p.ts.isoformat(),
                        names.get(p.target_id, p.target_id),
                        p.latency_avg_ms,
                        p.latency_max_ms,
                        p.jitter_ms,
                        p.packet_loss_pct,
                        p.samples,
                    ]
                    for p in pts
                ],
            )
        if kind == "events":
            evs = [
                EventOut.model_validate(e)
                for e in self._network.list_events(hours=hours, active_only=False, limit=500)
            ]
            return name, to_csv(
                ["inicio_utc", "fim_utc", "tipo", "severidade", "mensagem"],
                [
                    [
                        e.started_at.isoformat(),
                        e.ended_at.isoformat() if e.ended_at else "",
                        e.event_type,
                        e.severity,
                        e.message,
                    ]
                    for e in evs
                ],
            )
        if kind == "devices":
            devs = [
                DeviceOut.model_validate(d)
                for d in self._devices.list_devices(online=None, known=None)
            ]
            return name, to_csv(
                [
                    "ip",
                    "mac",
                    "nome",
                    "hostname",
                    "fabricante",
                    "categoria",
                    "conhecido",
                    "online",
                    "primeira_vez_utc",
                    "ultima_vez_utc",
                ],
                [
                    [
                        d.ip,
                        d.mac,
                        d.custom_name,
                        d.hostname,
                        d.vendor,
                        d.category,
                        "sim" if d.is_known else "não",
                        "sim" if d.online else "não",
                        d.first_seen.isoformat(),
                        d.last_seen.isoformat(),
                    ]
                    for d in devs
                ],
            )
        alerts = [
            AlertOut.model_validate(a)
            for a in self._alerts.list(status="all", severity=None, limit=500)
        ]
        return name, to_csv(
            ["criado_utc", "tipo", "severidade", "status", "titulo", "mensagem"],
            [
                [a.created_at.isoformat(), a.kind, a.severity, a.status, a.title, a.message]
                for a in alerts
                if _aware(a.created_at) >= datetime.now(UTC) - timedelta(hours=hours)
            ],
        )


def _check_hours(hours: int) -> None:
    if not 1 <= hours <= _MAX_HOURS:
        raise DomainValidationError(f"'hours' deve estar entre 1 e {_MAX_HOURS}")


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
