from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, utcnow


class MonitorTarget(Base):
    __tablename__ = "monitor_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    host: Mapped[str] = mapped_column(String(253))
    kind: Mapped[str] = mapped_column(String(16))  # gateway | external | dns
    method: Mapped[str] = mapped_column(String(8))  # icmp | tcp | dns
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class NetworkMetric(Base):
    __tablename__ = "network_metrics"
    __table_args__ = (Index("ix_network_metrics_target_ts", "target_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitor_targets.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    sent: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer)
    latency_min_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_avg_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_max_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    jitter_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    packet_loss_pct: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class NetworkEvent(Base):
    __tablename__ = "network_events"
    __table_args__ = (Index("ix_network_events_active", "ended_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_key: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(
        String(24)
    )  # internet_down|gateway_down|target_down|dns_down
    severity: Mapped[str] = mapped_column(String(16))  # info | warning | critical
    target_id: Mapped[int | None] = mapped_column(
        ForeignKey("monitor_targets.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
