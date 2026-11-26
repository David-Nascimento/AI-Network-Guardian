"""Restrição de destinos monitorados (proteção contra SSRF e varredura indevida)."""

from __future__ import annotations

import ipaddress
import re

from app.core.exceptions import DomainValidationError

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def validate_host(host: str, authorized_networks: list[Network]) -> str:
    """Devolve o host normalizado ou levanta DomainValidationError.

    - Nunca aceita loopback, link-local (metadados de nuvem), multicast ou não especificado.
    - IPs privados só são aceitos dentro das faixas autorizadas.
    - Nomes de host precisam ter sintaxe válida (impede injeção de argumentos no ping).
    """
    value = host.strip().lower()
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        if value.startswith("-") or not _HOSTNAME.match(value):
            raise DomainValidationError("Host inválido") from None
        return value

    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise DomainValidationError("Endereço não permitido como destino de monitoramento")
    if ip.is_private and not any(ip in net for net in authorized_networks):
        raise DomainValidationError("IP privado fora das faixas autorizadas")
    return str(ip)
