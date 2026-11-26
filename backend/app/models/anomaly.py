from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UTCDateTime, utcnow


class Anomaly(Base):
    """Janela de tempo que o modelo marcou como fora do padrão do próprio destino."""

    __tablename__ = "anomalies"
    __table_args__ = (
        UniqueConstraint("target_id", "window_start", name="uq_anomaly_target_window"),
        Index("ix_anomalies_window", "window_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("monitor_targets.id", ondelete="CASCADE"))
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)
    method: Mapped[str] = mapped_column(String(24))
    score: Mapped[float] = mapped_column(Float)
    features: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    deviations: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
