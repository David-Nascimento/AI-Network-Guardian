from __future__ import annotations

from dataclasses import replace

from app.services.connectivity import TargetHealth, classify


def h(tid: int, kind: str, down: bool) -> TargetHealth:
    return TargetHealth(tid, f"t{tid}", kind, down, 3 if down else 0)


def types(health: list[TargetHealth]) -> list[str]:
    return sorted(i.event_type for i in classify(health))


def test_all_healthy_no_incidents() -> None:
    assert classify([h(1, "gateway", False), h(2, "external", False), h(3, "dns", False)]) == []


def test_single_external_down_is_target_specific() -> None:
    assert types([h(1, "gateway", False), h(2, "external", True), h(3, "external", False)]) == [
        "target_down"
    ]


def test_all_externals_down_with_gateway_up_is_internet_down() -> None:
    incidents = classify([h(1, "gateway", False), h(2, "external", True), h(3, "external", True)])
    assert [i.event_type for i in incidents] == ["internet_down"]
    assert "provedor" in incidents[0].message
    assert len(incidents[0].details["targets"]) == 2  # type: ignore[arg-type]


def test_gateway_down_swallows_downstream_failures() -> None:
    health = [
        h(1, "gateway", True),
        h(2, "external", True),
        h(3, "external", True),
        h(4, "dns", True),
    ]
    assert types(health) == ["gateway_down"]


def test_dns_failure_with_internet_up() -> None:
    assert types([h(2, "external", False), h(3, "external", False), h(4, "dns", True)]) == [
        "dns_down"
    ]


def test_dns_failure_suppressed_when_internet_down() -> None:
    assert types([h(2, "external", True), h(3, "external", True), h(4, "dns", True)]) == [
        "internet_down"
    ]


def test_single_external_never_claims_internet_outage() -> None:
    assert types([h(2, "external", True)]) == ["target_down"]


def test_incident_keys_are_stable_for_deduplication() -> None:
    a = classify([h(2, "external", True), h(3, "external", False)])
    b = classify([h(2, "external", True), h(3, "external", False)])
    assert [i.key for i in a] == [i.key for i in b] == ["target_down:2"]


def test_dns_message_does_not_claim_internet_works_without_evidence() -> None:
    unknown = [replace(h(2, "external", False), known=False), h(4, "dns", True)]
    (incident,) = classify(unknown)
    assert incident.event_type == "dns_down"
    assert "conectividade externa" not in incident.message

    proven = [h(2, "external", False), h(4, "dns", True)]
    assert "conectividade externa ativa" in classify(proven)[0].message
