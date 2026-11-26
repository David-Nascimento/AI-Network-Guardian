from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DeviceCategory = Literal[
    "unknown", "computer", "smartphone", "tv", "iot", "network", "printer", "other"
]
DeviceStatus = Literal["online", "offline"]


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mac: str
    ip: str
    hostname: str | None
    vendor: str | None
    custom_name: str | None
    category: DeviceCategory
    is_known: bool
    online: bool
    first_seen: datetime
    last_seen: datetime
    ports_scanned_at: datetime | None = None


class DeviceUpdate(BaseModel):
    custom_name: str | None = Field(default=None, max_length=80)
    category: DeviceCategory | None = None
    is_known: bool | None = None


class DeviceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    detail: str | None
    ts: datetime


class ScanResult(BaseModel):
    network: str
    found: int
    new: int
    reconnected: int
    disconnected: int
    scanned_at: datetime


class BulkResult(BaseModel):
    updated: int


class PortOut(BaseModel):
    port: int
    service: str
    first_seen: datetime
    last_seen: datetime


class PortScanResult(BaseModel):
    scanned_at: datetime
    checked: int
    open_ports: list[PortOut]


class ImportNamesIn(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class ImportNamesResult(BaseModel):
    parsed: int
    matched: int
    updated: int
