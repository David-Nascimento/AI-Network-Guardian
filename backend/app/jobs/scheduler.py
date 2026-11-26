from __future__ import annotations

from collections.abc import Mapping

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import Probe
from app.collectors.arp_collector import NeighborScanner
from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.jobs.tasks import (
    run_anomaly_scan,
    run_collection_cycle,
    run_retention,
    run_scheduled_device_scan,
)
from app.websocket import EventBus


def build_scheduler(  # noqa: PLR0917
    session_factory: sessionmaker[Session],
    settings: Settings,
    probes: Mapping[str, Probe],
    scanner: NeighborScanner,
    oui: OuiDatabase,
    bus: EventBus | None = None,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_collection_cycle,
        "interval",
        seconds=settings.collect_interval_seconds,
        args=[session_factory, settings, probes, bus],
        id="collect",
        max_instances=1,
        coalesce=True,
    )
    if settings.scan_enabled:
        scheduler.add_job(
            run_scheduled_device_scan,
            "interval",
            seconds=settings.scan_interval_seconds,
            args=[session_factory, settings, scanner, oui, bus],
            id="device_scan",
            max_instances=1,
            coalesce=True,
        )
    if settings.ml_enabled:
        scheduler.add_job(
            run_anomaly_scan,
            "interval",
            minutes=settings.ml_interval_minutes,
            args=[session_factory, settings, bus],
            id="anomaly_scan",
            max_instances=1,
            coalesce=True,
        )
    scheduler.add_job(
        run_retention,
        "cron",
        hour=3,
        minute=15,
        args=[session_factory, settings],
        id="retention",
        max_instances=1,
    )
    return scheduler
