from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, utcnow


class Device(Base):
    """Dispositivo identificado pelo MAC. Sem MAC acessível, o dispositivo não é rastreado."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    mac: Mapped[str] = mapped_column(String(17), unique=True)
    ip: Mapped[str] = mapped_column(String(45))
    hostname: Mapped[str | None] = mapped_column(String(253), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    custom_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(16), default="unknown")
    is_known: Mapped[bool] = mapped_column(Boolean, default=False)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    missed_scans: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ports_scanned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class DeviceEvent(Base):
    __tablename__ = "device_events"
    __table_args__ = (Index("ix_device_events_device_ts", "device_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(16))  # connected | disconnected | ip_changed
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class DevicePort(Base):
    """Porta TCP aberta observada na última varredura de portas do dispositivo."""

    __tablename__ = "device_ports"
    __table_args__ = (UniqueConstraint("device_id", "port", name="uq_device_port"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    port: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
