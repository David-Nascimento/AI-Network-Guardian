from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentStatus(BaseModel):
    enabled: bool
    model: str | None
    reachable: bool
    model_installed: bool
    detail: str | None
    tools: list[str]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class ToolTraceOut(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    summary: str


class ChatResponse(BaseModel):
    answer: str
    stopped: Literal["answered", "max_steps"]
    steps: int
    tool_calls: list[ToolTraceOut]
