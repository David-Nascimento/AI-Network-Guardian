import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLiveEvents, invalidateFor, liveUrl } from "@/hooks/useLiveEvents";
import { Alerts } from "@/pages/Alerts";
import { authStore } from "@/stores/auth";
import { liveStore } from "@/stores/live";
import type { Alert, MetricPoint } from "@/types/api";
import { pivotMetric } from "@/utils/format";
import { mockFetch, renderApp } from "./helpers";

const alert = (over: Partial<Alert> = {}): Alert => ({
  id: 1,
  kind: "new_device",
  severity: "warning",
  title: "Novo dispositivo na rede",
  message: "Apareceu 192.168.0.10 (notebook). Ainda não foi marcado como conhecido.",
  device_id: 1,
  created_at: "2026-11-25T10:00:00Z",
  resolved_at: null,
  acknowledged_at: null,
  acknowledged_by: null,
  status: "new",
  ...over,
});

const rules = [
  { kind: "new_device", label: "Novo dispositivo", description: "Avisa quando aparece um aparelho.", enabled: true },
  { kind: "known_device_offline", label: "Conhecido offline", description: "Avisa quando cai.", enabled: false },
];
const mlStatus = (over: Record<string, unknown> = {}) => ({
  enabled: true,
  configured_method: "auto",
  effective_method: "robust_zscore",
  sklearn_available: false,
  window_minutes: 5,
  min_windows: 48,
  train_hours: 168,
  targets: [{ target_id: 1, name: "Cloudflare", windows: 60, ready: true }],
  ...over,
});
const ML = {
  "GET /api/v1/ml/status": { body: mlStatus() },
  "GET /api/v1/ml/anomalies": { body: [] },
};
const me = (role: string) => ({ "GET /api/v1/auth/me": { body: { id: 1, username: "u", role } } });

beforeEach(() => authStore.setToken("tok"));

describe("Alerts", () => {
  it("lista alertas, não presume malícia e permite reconhecer (admin)", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/alerts": { body: [alert()] },
      "GET /api/v1/alerts/rules": { body: rules },
      ...ML,
      "POST /api/v1/alerts/1/ack": { body: alert({ status: "acknowledged", acknowledged_by: "u" }) },
    });
    renderApp(<Alerts />);
    expect(await screen.findByText("Novo dispositivo na rede")).toBeInTheDocument();
    expect(screen.queryByText(/malicios|invasor|ataque/i)).toBeNull();
    await userEvent.click(await screen.findByRole("button", { name: /Reconhecer alerta/ }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/v1/alerts/1/ack")).toBe(true));
  });

  it("leitor não vê botões de ação nem edita regras", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/alerts": { body: [alert()] },
      "GET /api/v1/alerts/rules": { body: rules },
      ...ML,
    });
    renderApp(<Alerts />);
    await screen.findByText("Novo dispositivo na rede");
    expect(screen.queryByRole("button", { name: /Reconhecer/ })).toBeNull();
    expect(await screen.findByLabelText(/Novo dispositivo/)).toBeDisabled();
  });

  it("filtra por status usando a query da API", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/alerts": { body: [] },
      "GET /api/v1/alerts/rules": { body: rules },
      ...ML,
    });
    renderApp(<Alerts />);
    expect(await screen.findByText("Nenhum alerta neste filtro")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Filtrar alertas"), "resolved");
    await waitFor(() => expect(calls.some((c) => c.url.includes("status=resolved"))).toBe(true));
  });

  it("admin liga uma regra", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/alerts": { body: [] },
      "GET /api/v1/alerts/rules": { body: rules },
      ...ML,
      "PATCH /api/v1/alerts/rules/known_device_offline": { body: { ...rules[1], enabled: true } },
    });
    renderApp(<Alerts />);
    await userEvent.click(await screen.findByLabelText(/Conhecido offline/));
    await waitFor(() =>
      expect(calls.find((c) => c.key === "PATCH /api/v1/alerts/rules/known_device_offline")?.init?.body).toBe(
        JSON.stringify({ enabled: true }),
      ),
    );
  });
});

describe("AnomalyCard na página de Alertas", () => {
  it("mostra desvio com texto honesto e o método em uso", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/alerts": { body: [] },
      "GET /api/v1/alerts/rules": { body: rules },
      "GET /api/v1/ml/status": { body: mlStatus() },
      "GET /api/v1/ml/anomalies": {
        body: [
          {
            id: 1,
            target_id: 1,
            window_start: "2026-11-25T10:00:00Z",
            method: "robust_zscore",
            score: 9.1,
            features: {},
            deviations: ["latência média 95.0 ms (acima do normal ≈ 12.0 ms)"],
          },
        ],
      },
    });
    renderApp(<Alerts />);
    expect(await screen.findByText(/latência média 95\.0 ms/)).toBeInTheDocument();
    expect(screen.getByText(/estatística robusta/)).toBeInTheDocument();
    expect(screen.getByText(/Isolation Forest indisponível/)).toBeInTheDocument();
    expect(screen.getByText(/não indicam a causa/)).toBeInTheDocument();
  });

  it("avisa que ainda está aprendendo quando faltam dados", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/alerts": { body: [] },
      "GET /api/v1/alerts/rules": { body: rules },
      "GET /api/v1/ml/status": {
        body: mlStatus({ effective_method: null, targets: [{ target_id: 1, name: "Cloudflare", windows: 3, ready: false }] }),
      },
      "GET /api/v1/ml/anomalies": { body: [] },
    });
    renderApp(<Alerts />);
    expect(await screen.findByText(/Ainda aprendendo/)).toBeInTheDocument();
    expect(screen.getByText("Cloudflare: 3/48 janelas")).toBeInTheDocument();
  });
});

describe("invalidateFor / liveUrl", () => {
  it("invalida só o que o evento afeta e ignora tipos desconhecidos", () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    invalidateFor(qc, { type: "alert.created", data: {}, ts: null });
    expect(spy.mock.calls.map((c) => c[0]?.queryKey)).toEqual([["alerts"]]);
    spy.mockClear();
    invalidateFor(qc, { type: "network.updated", data: {}, ts: null });
    expect(spy.mock.calls.map((c) => c[0]?.queryKey?.[0])).toEqual(["network", "metrics", "topology", "alerts"]);
    spy.mockClear();
    invalidateFor(qc, { type: "qualquer.coisa", data: {}, ts: null });
    expect(spy).not.toHaveBeenCalled();
  });

  it("usa wss em https e ws em http", () => {
    expect(liveUrl({ protocol: "https:", host: "x.local" })).toBe("wss://x.local/api/v1/ws");
    expect(liveUrl({ protocol: "http:", host: "localhost:5173" })).toBe("ws://localhost:5173/api/v1/ws");
  });
});

class FakeSocket {
  static instances: FakeSocket[] = [];
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.onclose?.({ code: 1000 });
  }
}

function Harness({ children }: { children?: ReactNode }) {
  useLiveEvents();
  return <>{children}</>;
}

describe("useLiveEvents", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeSocket);
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const mount = () => {
    const client = new QueryClient();
    const spy = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <Harness />
      </QueryClientProvider>,
    );
    return spy;
  };

  it("autentica pela primeira mensagem (token fora da URL) e fica ao vivo no 'ready'", () => {
    mount();
    const ws = FakeSocket.instances[0]!;
    expect(ws.url).not.toContain("tok");
    ws.onopen?.();
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: "auth", token: "tok" });
    expect(liveStore.get()).toBe("connecting");
    ws.onmessage?.({ data: JSON.stringify({ type: "ready", data: {}, ts: null }) });
    expect(liveStore.get()).toBe("live");
  });

  it("reconecta com espera ao cair, mas não insiste se o token for recusado (4401)", () => {
    mount();
    FakeSocket.instances[0]!.onclose?.({ code: 1006 });
    expect(liveStore.get()).toBe("offline");
    vi.advanceTimersByTime(1_000);
    expect(FakeSocket.instances).toHaveLength(2);
    FakeSocket.instances[1]!.onclose?.({ code: 4401 });
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("evento chegando invalida as consultas certas", () => {
    const spy = mount();
    const ws = FakeSocket.instances[0]!;
    ws.onmessage?.({ data: JSON.stringify({ type: "alert.created", data: {}, ts: "x" }) });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["alerts"] });
  });

  it("sem sessão não abre conexão", () => {
    authStore.clear();
    mount();
    expect(FakeSocket.instances).toHaveLength(0);
  });
});

describe("pivotMetric", () => {
  it("monta uma coluna por destino para o campo escolhido", () => {
    const p = (ts: string, id: number, jitter: number | null, loss: number): MetricPoint => ({
      ts,
      target_id: id,
      latency_avg_ms: 10,
      latency_max_ms: 12,
      jitter_ms: jitter,
      packet_loss_pct: loss,
      samples: 4,
    });
    const points = [p("2026-11-25T10:05:00Z", 1, 2, 0), p("2026-11-25T10:00:00Z", 1, 1, 5), p("2026-11-25T10:00:00Z", 2, null, 0)];
    const targets = [{ id: 1, name: "A" }, { id: 2, name: "B" }];
    expect(pivotMetric(points, targets, "jitter_ms")).toEqual([
      { ts: "2026-11-25T10:00:00Z", A: 1, B: null },
      { ts: "2026-11-25T10:05:00Z", A: 2 },
    ]);
    expect(pivotMetric(points, targets, "packet_loss_pct")[0]).toMatchObject({ A: 5, B: 0 });
  });
});
