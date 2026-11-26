from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent import ProviderError, ToolContext, build_registry, run_agent
from app.api.dependencies import (
    CurrentUser,
    DbDep,
    LLMDep,
    OuiDep,
    SettingsDep,
    get_current_user,
)
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import audit
from app.schemas import AgentStatus, ChatRequest, ChatResponse, ToolTraceOut

router = APIRouter(prefix="/agent", tags=["agente"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=AgentStatus)
def status(llm: LLMDep) -> AgentStatus:
    tools = build_registry().names()
    if llm is None:
        return AgentStatus(
            enabled=False,
            model=None,
            reachable=False,
            model_installed=False,
            detail="Defina NG_OLLAMA_MODEL para ligar o agente.",
            tools=tools,
        )
    health = llm.health()
    return AgentStatus(
        enabled=True,
        model=llm.model,
        reachable=health.reachable,
        model_installed=health.model_installed,
        detail=health.detail,
        tools=tools,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(  # noqa: PLR0917
    body: ChatRequest,
    llm: LLMDep,
    db: DbDep,
    settings: SettingsDep,
    oui: OuiDep,
    user: CurrentUser,
) -> ChatResponse:
    if llm is None:
        raise ServiceUnavailableError("O agente está desligado (NG_OLLAMA_MODEL não definido).")
    try:
        result = run_agent(
            llm,
            build_registry(),
            ToolContext(db, settings, oui),
            body.message,
            [t.model_dump() for t in body.history],
            max_steps=settings.agent_max_steps,
        )
    except ProviderError as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    audit(
        "agent_chat",
        actor=user.username,
        question_chars=len(body.message),
        tools=[t.name for t in result.tool_calls],
        stopped=result.stopped,
    )
    return ChatResponse(
        answer=result.answer,
        stopped=result.stopped,
        steps=result.steps,
        tool_calls=[
            ToolTraceOut(name=t.name, arguments=t.arguments, ok=t.ok, summary=t.summary)
            for t in result.tool_calls
        ],
    )
