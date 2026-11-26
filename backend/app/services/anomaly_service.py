"""Detecção de anomalias por destino: aprende a linha de base e avalia janelas já fechadas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ml import FEATURES, Detector, Window, build_windows, make_detector, sklearn_available
from app.ml.features import Sample
from app.models import Anomaly, MonitorTarget
from app.repositories import AnomalyRepository, MetricRepository, TargetRepository
from app.schemas.ml import MlStatus, MlTargetStatus
from app.services.alert_service import AlertService

_MAX_SAMPLES = 60_000
_RECENT_WINDOWS = 3  # quantas janelas fechadas mais recentes são avaliadas a cada execução


class AnomalyService:
    def __init__(self, session: Session, settings: Settings, alerts: AlertService) -> None:
        self._settings = settings
        self._alerts = alerts
        self._targets = TargetRepository(session)
        self._metrics = MetricRepository(session)
        self._anomalies = AnomalyRepository(session)

    # ---- leitura ---------------------------------------------------------
    def _windows(self, target_id: int, now: datetime) -> list[Window]:
        rows = self._metrics.range(
            since=now - timedelta(hours=self._settings.ml_train_hours),
            until=now,
            target_id=target_id,
            limit=_MAX_SAMPLES,
        )
        samples = [
            Sample(r.ts, r.latency_avg_ms, r.latency_max_ms, r.jitter_ms, r.packet_loss_pct)
            for r in rows
        ]
        return build_windows(samples, self._settings.ml_window_minutes)

    def status(self, now: datetime | None = None) -> MlStatus:
        now = now or datetime.now(UTC)
        targets: list[MlTargetStatus] = []
        for t in self._targets.list(enabled_only=True):
            n = len(self._windows(t.id, now))
            targets.append(
                MlTargetStatus(
                    target_id=t.id, name=t.name, windows=n, ready=n >= self._settings.ml_min_windows
                )
            )
        most = max((t.windows for t in targets), default=0)
        effective = (
            make_detector(self._effective_pref(), rows=most).method
            if most >= self._settings.ml_min_windows
            else None
        )
        return MlStatus(
            enabled=self._settings.ml_enabled,
            configured_method=self._settings.ml_method,
            effective_method=effective,
            sklearn_available=sklearn_available(),
            window_minutes=self._settings.ml_window_minutes,
            min_windows=self._settings.ml_min_windows,
            train_hours=self._settings.ml_train_hours,
            targets=targets,
        )

    def recent(self, hours: int, limit: int, target_id: int | None) -> list[Anomaly]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        return self._anomalies.recent(since, limit, target_id)

    # ---- execução --------------------------------------------------------
    def _effective_pref(self) -> str:
        # Método pedido sem scikit-learn instalado: cai no estatístico, sem quebrar o job.
        pref = self._settings.ml_method
        return "robust_zscore" if pref == "isolation_forest" and not sklearn_available() else pref

    def scan(self, now: datetime | None = None) -> list[tuple[str, dict[str, Any]]]:
        """Avalia as últimas janelas fechadas de cada destino. Retorna eventos para o tempo real."""
        now = now or datetime.now(UTC)
        found = 0
        for target in self._targets.list(enabled_only=True):
            found += self._scan_target(target, now)
        events: list[tuple[str, dict[str, Any]]] = list(self._alerts.pending)
        if found:
            events.append(("anomalies.updated", {"new": found}))
        return events

    def _scan_target(self, target: MonitorTarget, now: datetime) -> int:
        windows = self._windows(target.id, now)
        current_start = now.replace(
            minute=now.minute - now.minute % self._settings.ml_window_minutes,
            second=0,
            microsecond=0,
        )
        closed = [w for w in windows if w.start < current_start]
        if len(closed) < self._settings.ml_min_windows:
            return 0
        recent = closed[-_RECENT_WINDOWS:]
        training = closed[: len(closed) - len(recent)] or closed
        detector: Detector = make_detector(self._effective_pref(), rows=len(training))
        detector.fit([w.values for w in training])

        key = f"anomaly:{target.id}"
        created = 0
        latest_anomalous = False
        for window in recent:
            verdict = detector.judge(window.values)
            latest_anomalous = verdict.anomalous
            if not verdict.anomalous or self._anomalies.exists(target.id, window.start):
                continue
            self._anomalies.add(
                Anomaly(
                    target_id=target.id,
                    window_start=window.start,
                    method=detector.method,
                    score=round(verdict.score, 4),
                    features=dict(zip(FEATURES, window.values, strict=True)),
                    deviations=[d.text() for d in verdict.deviations],
                )
            )
            created += 1
            self._alerts.raise_alert(
                kind="anomaly",
                dedupe_key=key,
                severity="warning",
                title=f"Comportamento fora do padrão: {target.name}",
                message="; ".join(d.text() for d in verdict.deviations)
                + ". É um desvio estatístico do histórico deste destino; não indica a causa.",
            )
        if not latest_anomalous:
            self._alerts.resolve(key)
        return created
