from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import (
    AdminUser,
    DeviceServiceDep,
    OuiDep,
    PortScannerDep,
    ScannerDep,
    SettingsDep,
    get_current_user,
)
from app.core.logging import audit
from app.jobs import run_device_scan
from app.schemas import (
    BulkResult,
    DeviceEventOut,
    DeviceOut,
    DeviceUpdate,
    ImportNamesIn,
    ImportNamesResult,
    PortOut,
    PortScanResult,
    ScanResult,
)

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DeviceOut])
def list_devices(
    service: DeviceServiceDep, online: bool | None = None, known: bool | None = None
) -> list[DeviceOut]:
    return [DeviceOut.model_validate(d) for d in service.list_devices(online=online, known=known)]


@router.post("/scan", response_model=ScanResult)
def scan_now(
    request: Request, settings: SettingsDep, scanner: ScannerDep, oui: OuiDep, admin: AdminUser
) -> ScanResult:
    result = run_device_scan(
        request.app.state.session_factory, settings, scanner, oui, request.app.state.bus
    )
    audit("device_scan", actor=admin.username, found=result.found, new=result.new)
    return result


@router.post("/mark-all-known", response_model=BulkResult)
def mark_all_known(service: DeviceServiceDep, admin: AdminUser) -> BulkResult:
    updated = service.mark_all_known()
    audit("devices_marked_known", actor=admin.username, updated=updated)
    return BulkResult(updated=updated)


@router.post("/import-names", response_model=ImportNamesResult)
def import_names(
    body: ImportNamesIn, service: DeviceServiceDep, admin: AdminUser
) -> ImportNamesResult:
    result = service.import_router_names(body.text)
    audit("device_names_imported", actor=admin.username, matched=result.matched)
    return result


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, service: DeviceServiceDep) -> DeviceOut:
    return DeviceOut.model_validate(service.get(device_id))


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: int, body: DeviceUpdate, service: DeviceServiceDep, admin: AdminUser
) -> DeviceOut:
    device = service.update(device_id, body)
    audit("device_updated", actor=admin.username, device_id=device_id)
    return DeviceOut.model_validate(device)


@router.get("/{device_id}/events", response_model=list[DeviceEventOut])
def device_events(
    device_id: int,
    service: DeviceServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[DeviceEventOut]:
    return [DeviceEventOut.model_validate(e) for e in service.events(device_id, limit)]


@router.get("/{device_id}/ports", response_model=list[PortOut])
def device_ports(device_id: int, service: DeviceServiceDep) -> list[PortOut]:
    return service.ports(device_id)


@router.post("/{device_id}/ports/scan", response_model=PortScanResult)
def scan_device_ports(
    device_id: int, service: DeviceServiceDep, scanner: PortScannerDep, admin: AdminUser
) -> PortScanResult:
    result = service.scan_ports(device_id, scanner)
    audit(
        "device_ports_scanned",
        actor=admin.username,
        device_id=device_id,
        open_ports=len(result.open_ports),
    )
    return result
