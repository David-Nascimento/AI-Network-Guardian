import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { Guardian } from "@/pages/Guardian";
import { authStore } from "@/stores/auth";
import { mockFetch, renderApp } from "./helpers";

const status = (over: Record<string, unknown> = {}) => ({
  enabled: true,
  model: "llama3.2",
  reachable: true,
  model_installed: true,
  detail: null,
  tools: ["a", "b"],
  ...over,
});

beforeEach(() => authStore.setToken("tok"));

describe("Guardian", () => {
  it("agente desligado: explica como ligar e bloqueia o envio", async () => {
    mockFetch({
      "GET /api/v1/agent/status": {
        body: status({ enabled: false, model: null, reachable: false, model_installed: false, detail: "Defina NG_OLLAMA_MODEL para ligar o agente." }),
      },
    });
    renderApp(<Guardian />);
    expect(await screen.findByText("Agente desligado")).toBeInTheDocument();
    expect(screen.getByText(/NG_OLLAMA_MODEL/)).toBeInTheDocument();
    expect(screen.getByLabelText("Pergunta")).toBeDisabled();
  });

  it("modelo ausente mostra o comando para instalar", async () => {
    mockFetch({
      "GET /api/v1/agent/status": { body: status({ model_installed: false, detail: "Modelo 'llama3.2' não instalado" }) },
    });
    renderApp(<Guardian />);
    expect(await screen.findByText("Modelo ausente")).toBeInTheDocument();
    expect(screen.getByText("ollama pull llama3.2")).toBeInTheDocument();
  });

  it("envia pergunta, mostra a resposta e as consultas feitas", async () => {
    const { calls } = mockFetch({
      "GET /api/v1/agent/status": { body: status() },
      "POST /api/v1/agent/chat": {
        body: {
          answer: "A internet está estável.",
          stopped: "answered",
          steps: 2,
          tool_calls: [{ name: "metrics_summary", arguments: { hours: 24 }, ok: true, summary: "320 caracteres" }],
        },
      },
    });
    renderApp(<Guardian />);
    await screen.findByText("Pronto");
    await userEvent.type(screen.getByLabelText("Pergunta"), "Como está a internet?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("A internet está estável.")).toBeInTheDocument();
    expect(screen.getByText(/Consultas feitas \(1\)/)).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.key === "POST /api/v1/agent/chat")?.init?.body));
    expect(sent).toEqual({ message: "Como está a internet?", history: [] });

    await userEvent.type(screen.getByLabelText("Pergunta"), "E ontem?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => {
      const second = calls.filter((c) => c.key === "POST /api/v1/agent/chat")[1];
      expect(JSON.parse(String(second?.init?.body)).history).toHaveLength(2);
    });
  });
});
