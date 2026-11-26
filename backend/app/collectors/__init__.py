from app.collectors.dns_collector import DnsProbe
from app.collectors.ping_collector import IcmpProbe, TcpProbe
from app.collectors.types import CollectorUnavailableError, Probe, ProbeResult

PROBE_METHODS = ("icmp", "tcp", "dns")


def build_probe_registry() -> dict[str, Probe]:
    return {"icmp": IcmpProbe(), "tcp": TcpProbe(), "dns": DnsProbe()}


__all__ = [
    "PROBE_METHODS",
    "CollectorUnavailableError",
    "Probe",
    "ProbeResult",
    "build_probe_registry",
]
