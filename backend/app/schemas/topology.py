from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

NodeKind = Literal["internet", "gateway", "device"]
Confidence = Literal["confirmed", "inferred"]


class TopologyNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    status: Literal["online", "offline", "unknown"]
    category: str | None = None
    ip: str | None = None
    device_id: int | None = None
    is_known: bool | None = None


class TopologyEdge(BaseModel):
    source: str
    target: str
    confidence: Confidence
    reason: str


class Topology(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    notes: list[str]
