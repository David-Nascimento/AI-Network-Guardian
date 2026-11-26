"""Dependências do FastAPI: sessão, usuário atual, papéis e serviços."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.agent import LLMProvider
from app.collectors.arp_collector import NeighborScanner
from app.collectors.oui import OuiDatabase
from app.collectors.port_scanner import PortScannerProtocol
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import SlidingWindowRateLimiter, decode_access_token
from app.repositories import UserRepository
from app.schemas import UserOut
from app.services import (
    AlertService,
    AnomalyService,
    AuthService,
    DeviceService,
    MetricsService,
    NetworkService,
    ReportService,
    TopologyService,
)

_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserOut:
    if credentials is None:
        raise AuthenticationError("Autenticação necessária")
    claims = decode_access_token(
        credentials.credentials, secret=settings.secret_key.get_secret_value()
    )
    user = UserRepository(db).get_by_username(str(claims["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("Usuário inexistente ou inativo")
    return UserOut.model_validate(user)


CurrentUser = Annotated[UserOut, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> UserOut:
    if user.role != "admin":
        raise PermissionDeniedError("Requer perfil de administrador")
    return user


AdminUser = Annotated[UserOut, Depends(require_admin)]


def login_rate_limit(request: Request) -> None:
    limiter: SlidingWindowRateLimiter = request.app.state.login_limiter
    limiter.check(request.client.host if request.client else "unknown")


def get_auth_service(db: DbDep, settings: SettingsDep) -> AuthService:
    return AuthService(db, settings)


def get_network_service(db: DbDep, settings: SettingsDep) -> NetworkService:
    return NetworkService(db, settings)


def get_metrics_service(db: DbDep) -> MetricsService:
    return MetricsService(db)


def get_oui(request: Request) -> OuiDatabase:
    oui: OuiDatabase = request.app.state.oui
    return oui


def get_scanner(request: Request) -> NeighborScanner:
    scanner: NeighborScanner = request.app.state.scanner
    return scanner


def get_llm(request: Request) -> LLMProvider | None:
    llm: LLMProvider | None = request.app.state.llm
    return llm


def get_port_scanner(request: Request) -> PortScannerProtocol:
    scanner: PortScannerProtocol = request.app.state.port_scanner
    return scanner


def get_alert_service(db: DbDep) -> AlertService:
    return AlertService(db)


def get_device_service(
    db: DbDep, settings: SettingsDep, oui: Annotated[OuiDatabase, Depends(get_oui)]
) -> DeviceService:
    return DeviceService(db, settings, oui)


def get_topology_service(
    db: DbDep, settings: SettingsDep, oui: Annotated[OuiDatabase, Depends(get_oui)]
) -> TopologyService:
    return TopologyService(db, settings, oui)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
NetworkServiceDep = Annotated[NetworkService, Depends(get_network_service)]
MetricsServiceDep = Annotated[MetricsService, Depends(get_metrics_service)]
DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]


def get_report_service(
    db: DbDep, settings: SettingsDep, oui: Annotated[OuiDatabase, Depends(get_oui)]
) -> ReportService:
    return ReportService(db, settings, oui)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
LLMDep = Annotated[LLMProvider | None, Depends(get_llm)]
OuiDep = Annotated[OuiDatabase, Depends(get_oui)]
AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


def get_anomaly_service(db: DbDep, settings: SettingsDep) -> AnomalyService:
    return AnomalyService(db, settings, AlertService(db))


AnomalyServiceDep = Annotated[AnomalyService, Depends(get_anomaly_service)]
TopologyServiceDep = Annotated[TopologyService, Depends(get_topology_service)]
ScannerDep = Annotated[NeighborScanner, Depends(get_scanner)]
PortScannerDep = Annotated[PortScannerProtocol, Depends(get_port_scanner)]
