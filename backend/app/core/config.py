"""Configuração central da aplicação, lida de variáveis de ambiente (prefixo NG_)."""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-secret-change-me-0123456789abcdef"  # noqa: S105
_MIN_SECRET_LEN = 32
_MIN_ADMIN_PASSWORD_LEN = 10
_MIN_COLLECT_INTERVAL = 5
_MIN_SCAN_INTERVAL = 30
_PRIVATE_RANGES = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NG_", env_file=".env", extra="ignore")

    app_name: str = "AI Network Guardian"
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "sqlite:///./guardian.db"

    secret_key: SecretStr = SecretStr(_DEV_SECRET)
    access_token_minutes: int = 60
    admin_username: str = "admin"
    admin_password: SecretStr | None = None

    cors_origins: str = "http://localhost:5180,http://localhost:5173"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60

    scheduler_enabled: bool = True
    collect_interval_seconds: int = 30
    ping_count: int = 4
    probe_timeout_seconds: float = 2.0
    failure_threshold: int = 3
    retention_days: int = 30

    gateway_host: str | None = None
    scan_enabled: bool = True
    scan_network: str | None = None  # ex.: 192.168.100.0/24; vazio = /24 da interface padrão
    scan_interval_seconds: int = 60
    offline_after_scans: int = 2
    reverse_dns: bool = True
    strict_presence: bool = True
    oui_file: str | None = None  # base de fabricantes (formato Nmap ou IEEE)
    authorized_networks: str = _PRIVATE_RANGES
    seed_default_targets: bool = True

    ollama_url: str = "http://localhost:11434"
    ollama_model: str | None = None  # vazio = agente desligado
    agent_max_steps: int = 5
    agent_timeout_seconds: float = 90.0

    ml_enabled: bool = True
    ml_method: Literal["auto", "isolation_forest", "robust_zscore"] = "auto"
    ml_interval_minutes: int = 5
    ml_window_minutes: int = 5
    ml_train_hours: int = 168
    ml_min_windows: int = 48

    @field_validator("secret_key", "admin_password", mode="before")
    @classmethod
    def _blank_means_unset(cls, value: object, info: ValidationInfo) -> object:
        """`NG_X=` vazio (como no .env.example) equivale a não definido."""
        if isinstance(value, str) and not value.strip():
            return _DEV_SECRET if info.field_name == "secret_key" else None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def authorized_network_list(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [
            ipaddress.ip_network(n.strip(), strict=False)
            for n in self.authorized_networks.split(",")
            if n.strip()
        ]

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        secret = self.secret_key.get_secret_value()
        if self.environment == "production" and (
            secret == _DEV_SECRET or len(secret) < _MIN_SECRET_LEN
        ):
            raise ValueError("NG_SECRET_KEY precisa ter 32+ caracteres e não pode ser o padrão")
        if (
            self.admin_password is not None
            and len(self.admin_password.get_secret_value()) < _MIN_ADMIN_PASSWORD_LEN
        ):
            raise ValueError("NG_ADMIN_PASSWORD precisa ter pelo menos 10 caracteres")
        if self.collect_interval_seconds < _MIN_COLLECT_INTERVAL:
            raise ValueError("NG_COLLECT_INTERVAL_SECONDS mínimo é 5")
        if self.scan_interval_seconds < _MIN_SCAN_INTERVAL or self.offline_after_scans < 1:
            raise ValueError(
                "NG_SCAN_INTERVAL_SECONDS mínimo é 30 e NG_OFFLINE_AFTER_SCANS mínimo é 1"
            )
        if self.failure_threshold < 1:
            raise ValueError("NG_FAILURE_THRESHOLD mínimo é 1")
        _ = self.authorized_network_list  # falha cedo se algum CIDR for inválido
        _validate_local_url(self.ollama_url)
        return self


def _validate_local_url(url: str) -> None:
    """O agente lê dados da rede; o modelo precisa estar na própria máquina ou na rede local."""
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("NG_OLLAMA_URL inválida (use http://host:porta)")
    try:
        ip = ipaddress.ip_address(host)
        local = ip.is_private or ip.is_loopback
    except ValueError:
        local = host == "localhost" or "." not in host  # nome de serviço (ex.: docker "ollama")
    if not local:
        raise ValueError("NG_OLLAMA_URL deve apontar para a própria máquina ou rede local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
