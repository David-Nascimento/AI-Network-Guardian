"""Inventário de dispositivos: reconciliação de varreduras, histórico e edição pelo usuário."""

from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.collectors.arp_collector import DiscoveredHost
from app.collectors.oui import OuiDatabase
from app.collectors.port_scanner import COMMON_PORTS, PortScannerProtocol
from app.core.config import Settings
from app.core.exceptions import DomainValidationError, NotFoundError
from app.models import Device, DeviceEvent
from app.repositories import DeviceRepository
from app.schemas import (
    DeviceUpdate,
    ImportNamesResult,
    PortOut,
    PortScanResult,
    ScanResult,
)
from app.services.alert_service import AlertService
from app.services.router_import import parse_router_table


class DeviceService:
    def __init__(self, session: Session, settings: Settings, oui: OuiDatabase) -> None:
        self._devices = DeviceRepository(session)
        self._settings = settings
        self._oui = oui
        self._alerts = AlertService(session)
        self._published: list[tuple[str, dict[str, Any]]] = []

    def drain_events(self) -> list[tuple[str, dict[str, Any]]]:
        """Eventos para o tempo real, a publicar só depois do commit."""
        events = [*self._published, *self._alerts.pending]
        self._published.clear()
        self._alerts.pending.clear()
        return events

    # ---- consulta e edição ---------------------------------------------
    def list_devices(self, *, online: bool | None, known: bool | None) -> list[Device]:
        return self._devices.find(online=online, known=known)

    def get(self, device_id: int) -> Device:
        device = self._devices.get(device_id)
        if device is None:
            raise NotFoundError("Dispositivo não encontrado")
        return device

    def update(self, device_id: int, data: DeviceUpdate) -> Device:
        device = self.get(device_id)
        fields = data.model_fields_set
        if "custom_name" in fields:  # permite limpar o nome enviando null ou vazio
            device.custom_name = (data.custom_name or "").strip() or None
        if "category" in fields and data.category is not None:
            device.category = data.category
        if "is_known" in fields and data.is_known is not None:
            device.is_known = data.is_known
            if data.is_known:
                self._alerts.resolve_device(device.id, "new_device")
        return device

    def mark_all_known(self) -> int:
        self._alerts.resolve_kind("new_device")
        return self._devices.mark_all_known()

    def events(self, device_id: int, limit: int) -> list[DeviceEvent]:
        self.get(device_id)
        return self._devices.events(device_id, limit)

    # ---- nomes do roteador ---------------------------------------------
    def import_router_names(self, text: str) -> ImportNamesResult:
        """Aplica nomes de uma tabela DHCP colada pelo usuário. O MAC é a chave; sem MAC, o IP."""
        entries = parse_router_table(text)
        devices = self._devices.find()
        by_mac = {d.mac: d for d in devices}
        by_ip = {d.ip: d for d in devices}
        matched = updated = 0
        for entry in entries:
            device = by_mac.get(entry.mac) if entry.mac else None
            if device is None and entry.mac is None and entry.ip:
                device = by_ip.get(entry.ip)
            if device is None:
                continue
            matched += 1
            if device.hostname != entry.name:
                device.hostname = entry.name
                updated += 1
        return ImportNamesResult(parsed=len(entries), matched=matched, updated=updated)

    # ---- portas ----------------------------------------------------------
    def ports(self, device_id: int) -> list[PortOut]:
        self.get(device_id)
        return [
            self._port_out(p.port, p.first_seen, p.last_seen)
            for p in self._devices.ports(device_id)
        ]

    def scan_ports(
        self, device_id: int, scanner: PortScannerProtocol, *, now: datetime | None = None
    ) -> PortScanResult:
        device = self.get(device_id)
        ip = ipaddress.ip_address(device.ip)
        authorized = any(ip in net for net in self._settings.authorized_network_list)
        if not ip.is_private or not authorized:
            raise DomainValidationError("Só é permitido varrer portas de IPs privados autorizados")
        now = now or datetime.now(UTC)
        open_ports = scanner.scan(device.ip)
        rows = self._devices.replace_ports(device_id, open_ports, now)
        device.ports_scanned_at = now
        return PortScanResult(
            scanned_at=now,
            checked=len(COMMON_PORTS),
            open_ports=[self._port_out(p.port, p.first_seen, p.last_seen) for p in rows],
        )

    @staticmethod
    def _port_out(port: int, first_seen: datetime, last_seen: datetime) -> PortOut:
        return PortOut(
            port=port,
            service=COMMON_PORTS.get(port, "desconhecido"),
            first_seen=first_seen,
            last_seen=last_seen,
        )

    # ---- reconciliação --------------------------------------------------
    def apply_scan(
        self, network: str, hosts: list[DiscoveredHost], *, now: datetime | None = None
    ) -> ScanResult:
        now = now or datetime.now(UTC)
        existing = self._devices.by_mac()
        seen: set[str] = set()
        new = reconnected = disconnected = 0

        for host in hosts:
            seen.add(host.mac)
            device = existing.get(host.mac)
            if device is None:
                device = self._devices.add(
                    Device(
                        mac=host.mac,
                        ip=host.ip,
                        hostname=host.hostname,
                        vendor=self._oui.lookup(host.mac),
                        first_seen=now,
                        last_seen=now,
                    )
                )
                self._event(device, "connected", "primeira detecção", now)
                self._alert_new_device(device, now)
                new += 1
                continue
            if not device.online:
                device.online = True
                self._event(device, "connected", "voltou à rede", now)
                self._alerts.resolve(f"offline:{device.id}", now)
                reconnected += 1
            if device.ip != host.ip:
                self._event(device, "ip_changed", f"{device.ip} → {host.ip}", now)
                device.ip = host.ip
            device.hostname = host.hostname or device.hostname
            device.vendor = device.vendor or self._oui.lookup(host.mac)
            device.last_seen = now
            device.missed_scans = 0

        for mac, device in existing.items():
            if mac in seen or not device.online:
                continue
            device.missed_scans += 1
            if device.missed_scans >= self._settings.offline_after_scans:
                device.online = False
                self._event(device, "disconnected", "sem resposta nas últimas varreduras", now)
                self._alert_offline(device, now)
                disconnected += 1

        return ScanResult(
            network=network,
            found=len(hosts),
            new=new,
            reconnected=reconnected,
            disconnected=disconnected,
            scanned_at=now,
        )

    @staticmethod
    def _label(device: Device) -> str:
        return device.custom_name or device.hostname or device.vendor or device.ip

    def _event(self, device: Device, kind: str, detail: str, ts: datetime) -> None:
        self._devices.add_event(
            DeviceEvent(device_id=device.id, event_type=kind, detail=detail, ts=ts)
        )
        self._published.append(
            (
                "device.event",
                {
                    "device_id": device.id,
                    "label": self._label(device),
                    "ip": device.ip,
                    "event_type": kind,
                    "detail": detail,
                },
            )
        )

    def _alert_new_device(self, device: Device, now: datetime) -> None:
        self._alerts.raise_alert(
            kind="new_device",
            dedupe_key=f"new_device:{device.id}",
            severity="warning",
            title=f"Novo dispositivo: {self._label(device)}",
            message=(
                f"{device.ip} · MAC {device.mac} · {device.vendor or 'fabricante desconhecido'}. "
                "Não reconhecido não significa malicioso: confirme se o aparelho é seu e marque "
                "como conhecido."
            ),
            device_id=device.id,
            now=now,
        )

    def _alert_offline(self, device: Device, now: datetime) -> None:
        if not device.is_known:
            return
        self._alerts.raise_alert(
            kind="known_device_offline",
            dedupe_key=f"offline:{device.id}",
            severity="info",
            title=f"Saiu da rede: {self._label(device)}",
            message=f"{device.ip} (MAC {device.mac}) ficou sem resposta nas últimas varreduras.",
            device_id=device.id,
            now=now,
        )
