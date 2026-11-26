"""Monta o grafo da rede só com o que foi observado, marcando o que é inferência.

Com dados de camada 3 (ARP/ping) não dá para saber se um aparelho está no Wi-Fi, no cabo ou atrás de
um switch. Por isso as ligações dispositivo↔gateway são sempre `inferred`. Só a ligação
internet↔gateway pode ser `confirmed`, quando o monitoramento mostra os dois respondendo.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.models import Device
from app.repositories import DeviceRepository
from app.schemas import NetworkStatus, Topology, TopologyEdge, TopologyNode
from app.services.network_service import NetworkService

_LAN_REASON = (
    "Mesma rede local observada via ARP; o meio físico (Wi-Fi, cabo ou switch) é desconhecido."
)


class TopologyService:
    def __init__(self, session: Session, settings: Settings, oui: OuiDatabase) -> None:
        self._devices = DeviceRepository(session)
        self._network = NetworkService(session, settings)
        self._settings = settings
        _ = oui  # reservado: a topologia usa apenas dados já gravados

    def build(self) -> Topology:
        status = self._network.status()
        devices = self._devices.find()
        gateway_ip, gateway_status = self._gateway(status)
        gateway_device = (
            next((d for d in devices if d.ip == gateway_ip), None) if gateway_ip else None
        )

        internet_status = {"online": "online", "offline": "offline"}.get(status.state, "unknown")
        nodes = [
            TopologyNode(id="internet", kind="internet", label="Internet", status=internet_status),  # type: ignore[arg-type]
            self._gateway_node(gateway_ip, gateway_status, gateway_device),
        ]
        edges = [self._internet_edge(internet_status, gateway_status)]

        for d in devices:
            if gateway_device is not None and d.id == gateway_device.id:
                continue  # já representado pelo nó do gateway
            nodes.append(
                TopologyNode(
                    id=f"device-{d.id}",
                    kind="device",
                    label=d.custom_name or d.hostname or d.vendor or d.ip,
                    status="online" if d.online else "offline",
                    category=d.category,
                    ip=d.ip,
                    device_id=d.id,
                    is_known=d.is_known,
                )
            )
            edges.append(
                TopologyEdge(
                    source="gateway",
                    target=f"device-{d.id}",
                    confidence="inferred",
                    reason=_LAN_REASON,
                )
            )
        return Topology(nodes=nodes, edges=edges, notes=self._notes(gateway_ip, devices))

    # ---- internos -------------------------------------------------------
    def _gateway(self, status: NetworkStatus) -> tuple[str | None, str]:
        monitored = next((t for t in status.targets if t.target.kind == "gateway"), None)
        if monitored is None:
            return self._settings.gateway_host, "unknown"
        if monitored.last_sample_at is None:
            return monitored.target.host, "unknown"
        return monitored.target.host, "offline" if monitored.down else "online"

    @staticmethod
    def _gateway_node(ip: str | None, status: str, device: Device | None) -> TopologyNode:
        return TopologyNode(
            id="gateway",
            kind="gateway",
            label=(device.custom_name if device and device.custom_name else "Gateway")
            if ip
            else "Gateway (não configurado)",
            status=status,  # type: ignore[arg-type]
            ip=ip,
            device_id=device.id if device else None,
            is_known=device.is_known if device else None,
        )

    @staticmethod
    def _internet_edge(internet: str, gateway: str) -> TopologyEdge:
        if internet == "online" and gateway == "online":
            return TopologyEdge(
                source="internet",
                target="gateway",
                confidence="confirmed",
                reason="Gateway e destinos externos respondem no monitoramento.",
            )
        return TopologyEdge(
            source="internet",
            target="gateway",
            confidence="inferred",
            reason="Assume-se que a internet sai pelo gateway; nenhuma medição confirma isso.",
        )

    @staticmethod
    def _notes(gateway_ip: str | None, devices: list[Device]) -> list[str]:
        notes = ["Dispositivos sem MAC acessível e o próprio coletor não aparecem."]
        if gateway_ip is None:
            notes.append(
                "Gateway não configurado: defina NG_GATEWAY_HOST ou cadastre um destino gateway."
            )
        if not devices:
            notes.append("Nenhum dispositivo descoberto ainda: aguarde a primeira varredura.")
        return notes
