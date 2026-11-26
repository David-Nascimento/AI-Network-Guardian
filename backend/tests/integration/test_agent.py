from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.agent import LLMReply, ToolCall
from app.collectors.oui import OuiDatabase
from app.core.config import Settings
from app.main import create_app
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER, FakeProbe, FakeScanner
from tests.unit.test_agent import ScriptedLLM

API = "/api/v1"


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM([])


@pytest.fixture
def agent_client(
    settings: Settings, engine: Engine, probe: FakeProbe, scanner: FakeScanner, llm: ScriptedLLM
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        engine=engine,
        probes={"icmp": probe, "tcp": probe, "dns": probe},
        scanner=scanner,
        oui=OuiDatabase({}),
        llm=llm,
    )
    with TestClient(app) as c:
        yield c


def login(client: TestClient) -> dict[str, str]:
    r = client.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_agent_disabled_without_model(client: TestClient, auth: dict[str, str]) -> None:
    st = client.get(f"{API}/agent/status", headers=auth).json()
    assert st["enabled"] is False and "NG_OLLAMA_MODEL" in st["detail"] and len(st["tools"]) == 8
    r = client.post(f"{API}/agent/chat", json={"message": "oi"}, headers=auth)
    assert r.status_code == 503


def test_chat_uses_real_tool_and_returns_trace(agent_client: TestClient, llm: ScriptedLLM) -> None:
    h = login(agent_client)
    llm.replies = [
        LLMReply("", [ToolCall("network_status", {})]),
        LLMReply("A conexão está sendo monitorada."),
    ]
    r = agent_client.post(f"{API}/agent/chat", json={"message": "como está a internet?"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "A conexão está sendo monitorada." and body["stopped"] == "answered"
    assert body["tool_calls"][0]["name"] == "network_status" and body["tool_calls"][0]["ok"]
    st = agent_client.get(f"{API}/agent/status", headers=h).json()
    assert st["enabled"] and st["model"] == "fake" and st["model_installed"]


def test_chat_validates_input_and_requires_auth(agent_client: TestClient) -> None:
    h = login(agent_client)
    assert (
        agent_client.post(f"{API}/agent/chat", json={"message": ""}, headers=h).status_code == 422
    )
    assert (
        agent_client.post(
            f"{API}/agent/chat",
            json={"message": "x", "history": [{"role": "system", "content": "y"}]},
            headers=h,
        ).status_code
        == 422
    )
    assert agent_client.post(f"{API}/agent/chat", json={"message": "oi"}).status_code == 401
    assert agent_client.get(f"{API}/agent/status").status_code == 401
