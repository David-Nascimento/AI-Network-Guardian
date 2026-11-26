"""Importa todos os modelos para que o metadata do SQLAlchemy/Alembic os enxergue."""

from app.models.alert import Alert, AlertRule
from app.models.anomaly import Anomaly
from app.models.device import Device, DeviceEvent, DevicePort
from app.models.network import MonitorTarget, NetworkEvent, NetworkMetric
from app.models.user import User

__all__ = [
    "Alert",
    "AlertRule",
    "Anomaly",
    "Device",
    "DeviceEvent",
    "DevicePort",
    "MonitorTarget",
    "NetworkEvent",
    "NetworkMetric",
    "User",
]
