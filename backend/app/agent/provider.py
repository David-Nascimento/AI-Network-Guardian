"""Provedores de LLM. Só o Ollama local está implementado; o Protocol permite trocar/testar."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Falha ao falar com o modelo (fora do ar, modelo ausente, resposta inválida)."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    reachable: bool
    model_installed: bool
    detail: str | None = None


class LLMProvider(Protocol):
    model: str

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply: ...

    def health(self) -> ProviderHealth: ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout

    def _request(self, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        if not self._base.startswith(("http://", "https://")):
            raise ProviderError("URL do Ollama inválida")
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(  # noqa: S310 - esquema validado acima
            f"{self._base}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Ollama respondeu HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError("Não foi possível falar com o Ollama") from exc
        except ValueError as exc:
            raise ProviderError("Resposta inválida do Ollama") from exc
        if not isinstance(body, dict):
            raise ProviderError("Resposta inválida do Ollama")
        return body

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False}
        message = self._request("/api/chat", payload, self._timeout).get("message")
        if not isinstance(message, dict):
            raise ProviderError("Resposta do Ollama sem mensagem")
        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function", {}) if isinstance(raw, dict) else {}
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if fn.get("name"):
                calls.append(ToolCall(str(fn["name"]), args if isinstance(args, dict) else {}))
        return LLMReply(str(message.get("content") or ""), calls)

    def health(self) -> ProviderHealth:
        try:
            body = self._request("/api/tags", None, 2.0)
        except ProviderError as exc:
            return ProviderHealth(False, False, str(exc))
        names = {str(m.get("name", "")) for m in body.get("models", []) if isinstance(m, dict)}
        installed = self.model in names or f"{self.model}:latest" in names
        return ProviderHealth(
            True, installed, None if installed else f"Modelo '{self.model}' não instalado"
        )
