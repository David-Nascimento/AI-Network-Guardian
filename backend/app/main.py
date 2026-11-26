"""Ponto de entrada. Execute com: uvicorn --factory app.main:create_app"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.agent import LLMProvider, OllamaProvider
from app.api.routes import api_router, health
from app.collectors import Probe, build_probe_registry
from app.collectors.arp_collector import ArpScanner, NeighborScanner
from app.collectors.oui import OuiDatabase, resolve_oui_path
from app.collectors.port_scanner import PortScannerProtocol, TcpPortScanner
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import install_middleware
from app.core.security import SlidingWindowRateLimiter
from app.database.session import build_engine, build_session_factory
from app.jobs import build_scheduler
from app.services import AlertService, AuthService, NetworkService
from app.websocket import EventBus

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    probes: Mapping[str, Probe] | None = None,
    scanner: NeighborScanner | None = None,
    oui: OuiDatabase | None = None,
    port_scanner: PortScannerProtocol | None = None,
    llm: LLMProvider | None = None,
) -> FastAPI:
    """Fábrica da aplicação. `engine`, `probes`, `scanner` e `oui` servem à injeção em testes."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    engine = engine or build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    probe_registry = dict(probes) if probes is not None else build_probe_registry()
    device_scanner = scanner or ArpScanner(
        reverse_dns=settings.reverse_dns, strict=settings.strict_presence
    )
    oui_db = oui if oui is not None else OuiDatabase.from_file(resolve_oui_path(settings.oui_file))
    ports_scanner = port_scanner or TcpPortScanner()
    llm_provider = llm or (
        OllamaProvider(settings.ollama_url, settings.ollama_model, settings.agent_timeout_seconds)
        if settings.ollama_model
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with session_factory() as session:
            AuthService(session, settings).bootstrap_admin()
            AlertService(session).seed_rules()
            if settings.seed_default_targets:
                NetworkService(session, settings).seed_defaults()
            session.commit()
        app.state.bus.attach_loop(asyncio.get_running_loop())
        if settings.scheduler_enabled:
            scheduler = build_scheduler(
                session_factory, settings, probe_registry, device_scanner, oui_db, app.state.bus
            )
            scheduler.start()
            app.state.scheduler = scheduler
        try:
            yield
        finally:
            scheduler = getattr(app.state, "scheduler", None)
            if scheduler is not None:
                scheduler.shutdown(wait=False)
            engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.scanner = device_scanner
    app.state.oui = oui_db
    app.state.port_scanner = ports_scanner
    app.state.bus = EventBus()
    app.state.llm = llm_provider
    app.state.login_limiter = SlidingWindowRateLimiter(
        settings.login_rate_limit, settings.login_rate_window_seconds
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    install_middleware(app)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    return app
