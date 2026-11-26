import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { RequireAuth } from "@/components/layout/RequireAuth";
import { TargetsPanel } from "@/components/network/TargetsPanel";
import { Dashboard } from "@/pages/Dashboard";
import { Login } from "@/pages/Login";
import { authStore } from "@/stores/auth";
import { mockFetch, renderApp, target } from "./helpers";

const summary = {
  since: "2026-11-24T00:00:00Z",
  until: "2026-11-25T00:00:00Z",
  samples: 120,
  availability_pct: 99.2,
  latency_min_ms: 4.1,
  latency_avg_ms: 18.4,
  latency_max_ms: 60,
  jitter_avg_ms: 2.2,
  packet_loss_avg_pct: 0.5,
};

describe("autenticação", () => {
  it("redireciona para o login sem token", () => {
    renderApp(
      <Routes>
        <Route path="/login" element={<div>tela de login</div>} />
        <Route element={<RequireAuth />}>
          <Route index element={<div>privado</div>} />
        </Route>
      </Routes>,
    );
    expect(screen.getByText("tela de login")).toBeInTheDocument();
    expect(screen.queryByText("privado")).not.toBeInTheDocument();
  });

  it("login com sucesso guarda o token", async () => {
    mockFetch({ "POST /api/v1/auth/login": { body: { access_token: "tok", token_type: "bearer", expires_in: 3600 } } });
    renderApp(<Login />);
    await userEvent.type(screen.getByLabelText("Usuário"), "admin");
    await userEvent.type(screen.getByLabelText("Senha"), "segredo");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(authStore.getToken()).toBe("tok"));
  });

  it("mostra a mensagem do servidor quando as credenciais falham", async () => {
    mockFetch({
      "POST /api/v1/auth/login": { status: 401, body: { error: { code: "unauthorized", message: "Usuário ou senha inválidos" } } },
    });
    renderApp(<Login />);
    await userEvent.type(screen.getByLabelText("Usuário"), "admin");
    await userEvent.type(screen.getByLabelText("Senha"), "errada");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Usuário ou senha inválidos");
    expect(authStore.getToken()).toBeNull();
  });
});

describe("Dashboard", () => {
  it("exibe somente dados vindos da API", async () => {
    mockFetch({
      "GET /api/v1/network/status": {
        body: {
          state: "online",
          summary: "Todos os destinos monitorados estão respondendo.",
          checked_at: "2026-11-25T12:00:00Z",
          targets: [{ target: target(), down: false, last_sample_at: "2026-11-25T12:00:00Z", latency_avg_ms: 12, packet_loss_pct: 0 }],
          active_events: [],
        },
      },
      "GET /api/v1/metrics/summary": { body: summary },
      "GET /api/v1/metrics/history": { body: [] },
      "GET /api/v1/network/events": { body: [] },
    });
    renderApp(<Dashboard />);
    expect(await screen.findByText("18 ms")).toBeInTheDocument();
    expect(screen.getByText("99.2%")).toBeInTheDocument();
    expect(screen.getByText("Todos os destinos monitorados estão respondendo.")).toBeInTheDocument();
    expect(screen.getByText("Sem medições no período")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma interrupção no período")).toBeInTheDocument();
  });

  it("mostra erro com opção de tentar novamente quando a API falha", async () => {
    mockFetch({
      "GET /api/v1/network/status": { status: 500, body: { error: { code: "internal_error", message: "Erro interno do servidor" } } },
      "GET /api/v1/metrics/summary": { body: summary },
      "GET /api/v1/metrics/history": { body: [] },
      "GET /api/v1/network/events": { body: [] },
    });
    renderApp(<Dashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Erro interno do servidor");
    expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeInTheDocument();
  });
});

describe("TargetsPanel", () => {
  it("visitante não vê o formulário nem as ações", async () => {
    mockFetch({ "GET /api/v1/network/targets": { body: [target()] } });
    renderApp(<TargetsPanel isAdmin={false} />);
    expect(await screen.findByText("Cloudflare")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Adicionar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remover/ })).not.toBeInTheDocument();
  });

  it("admin cria destino TCP enviando a porta", async () => {
    const { calls } = mockFetch({
      "GET /api/v1/network/targets": { body: [] },
      "POST /api/v1/network/targets": { status: 201, body: target({ id: 2 }) },
    });
    renderApp(<TargetsPanel isAdmin />);
    await userEvent.type(await screen.findByLabelText("Nome"), "Roteador");
    await userEvent.type(screen.getByLabelText("Host ou IP"), "192.168.100.1");
    await userEvent.selectOptions(screen.getByLabelText("Método"), "tcp");
    await userEvent.type(screen.getByLabelText("Porta (TCP)"), "53");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/v1/network/targets")).toBe(true));
    const post = calls.find((c) => c.key === "POST /api/v1/network/targets");
    expect(JSON.parse(String(post?.init?.body))).toEqual({
      name: "Roteador", host: "192.168.100.1", kind: "external", method: "tcp", port: 53, enabled: true,
    });
  });

  it("tipo DNS força o método DNS e desabilita a porta", async () => {
    mockFetch({ "GET /api/v1/network/targets": { body: [] } });
    renderApp(<TargetsPanel isAdmin />);
    await userEvent.selectOptions(await screen.findByLabelText("Tipo"), "dns");
    expect(screen.getByLabelText("Método")).toBeDisabled();
    expect(screen.getByLabelText("Porta (TCP)")).toBeDisabled();
  });

  it("exibe o erro de validação do servidor (ex.: SSRF)", async () => {
    mockFetch({
      "GET /api/v1/network/targets": { body: [] },
      "POST /api/v1/network/targets": {
        status: 422,
        body: { error: { code: "validation_error", message: "Endereço não permitido como destino de monitoramento" } },
      },
    });
    renderApp(<TargetsPanel isAdmin />);
    await userEvent.type(await screen.findByLabelText("Nome"), "x");
    await userEvent.type(screen.getByLabelText("Host ou IP"), "169.254.169.254");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Endereço não permitido");
  });
});
