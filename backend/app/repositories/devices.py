from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Device, DeviceEvent, DevicePort


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, device_id: int) -> Device | None:
        return self._s.get(Device, device_id)

    def find(self, *, online: bool | None = None, known: bool | None = None) -> list[Device]:
        stmt = select(Device).order_by(Device.id)
        if online is not None:
            stmt = stmt.where(Device.online.is_(online))
        if known is not None:
            stmt = stmt.where(Device.is_known.is_(known))
        return list(self._s.scalars(stmt))

    def by_mac(self) -> dict[str, Device]:
        return {d.mac: d for d in self._s.scalars(select(Device))}

    def add(self, device: Device) -> Device:
        self._s.add(device)
        self._s.flush()
        return device

    def mark_all_known(self) -> int:
        result = self._s.execute(
            update(Device).where(Device.is_known.is_(False)).values(is_known=True)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def add_event(self, event: DeviceEvent) -> None:
        self._s.add(event)

    def events(self, device_id: int, limit: int) -> list[DeviceEvent]:
        return list(
            self._s.scalars(
                select(DeviceEvent)
                .where(DeviceEvent.device_id == device_id)
                .order_by(DeviceEvent.ts.desc(), DeviceEvent.id.desc())
                .limit(limit)
            )
        )

    def ports(self, device_id: int) -> list[DevicePort]:
        return list(
            self._s.scalars(
                select(DevicePort)
                .where(DevicePort.device_id == device_id)
                .order_by(DevicePort.port)
            )
        )

    def replace_ports(
        self, device_id: int, open_ports: list[int], now: datetime
    ) -> list[DevicePort]:
        """Mantém first_seen das portas que continuam abertas e remove as que fecharam."""
        current = {p.port: p for p in self.ports(device_id)}
        stale = [p for p in current if p not in open_ports]
        if stale:
            self._s.execute(
                delete(DevicePort).where(
                    DevicePort.device_id == device_id, DevicePort.port.in_(stale)
                )
            )
        for port in open_ports:
            if port in current:
                current[port].last_seen = now
            else:
                self._s.add(
                    DevicePort(device_id=device_id, port=port, first_seen=now, last_seen=now)
                )
        self._s.flush()
        return self.ports(device_id)
