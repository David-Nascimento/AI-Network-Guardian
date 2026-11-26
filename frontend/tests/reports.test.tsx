import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatDowntime, Reports } from "@/pages/Reports";
import { authStore } from "@/stores/auth";
import type { ReportSummary } from "@/types/api";
import { mockFetch, renderApp } from "./helpers";

const report: ReportSummary = {
  generated_at: "2026-11-25T12:00:00Z",
  since: "2026-11-24T12:00:00Z",
  until: "2026-11-25T12:00:00Z",
  hours: 24,
  availability_pct: 99.5,
  latency_avg_ms: 14.2,
  latency_max_ms: 80,
  jitter_avg_ms: 2.1,
  packet_loss_avg_pct: 0.3,
  samples: 2800,
  targets: [{ target_id: 1, name: "Cloudflare", availability_pct: 99.9, latency_avg_ms: 12, packet_loss_avg_pct: 0, samples: 1400 }],
  incidents: { count: 2, downtime_seconds: 190, by_type: { internet_down: 2 } },
  devices: { total: 10, online: 8, known: 3, unknown: 7, first_seen_in_period: 1 },
  alerts: { created: 4, by_kind: { new_device: 4 }, still_active: 2 },
  anomalies: 1,
  notes: ["Valores medidos pelos destinos monitorados; nada é estimado."],
};

beforeEach(() => authStore.setToken("tok"));

describe("Reports", () => {
  it("mostra o resumo com dados reais e a nota de que nada é estimado", async () => {
    mockFetch({ "GET /api/v1/reports/summary": { body: report } });
    renderApp(<Reports />);
    expect(await screen.findByText("99.5%")).toBeInTheDocument();
    expect(screen.getByText(/tempo total: 3 min/)).toBeInTheDocument();
    expect(screen.getByText("Cloudflare")).toBeInTheDocument();
    expect(screen.getByText(/7 ainda não reconhecidos/)).toBeInTheDocument();
    expect(screen.getByText(/pelos destinos monitorados/)).toBeInTheDocument();
  });

  it("troca o período e consulta de novo", async () => {
    const { calls } = mockFetch({ "GET /api/v1/reports/summary": { body: report } });
    renderApp(<Reports />);
    await screen.findByText("Cloudflare");
    await userEvent.selectOptions(screen.getByLabelText("Período do relatório"), "168");
    await waitFor(() => expect(calls.some((c) => c.url.includes("hours=168"))).toBe(true));
  });

  it("exporta CSV com o token no cabeçalho (não na URL)", async () => {
    const { calls } = mockFetch({
      "GET /api/v1/reports/summary": { body: report },
      "GET /api/v1/reports/export": () => ({ body: "a,b" }),
    });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    renderApp(<Reports />);
    await screen.findByText("Cloudflare");
    await userEvent.click(screen.getByRole("button", { name: "Dispositivos (CSV)" }));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled());
    const call = calls.find((c) => c.key === "GET /api/v1/reports/export");
    expect(call?.url).toContain("kind=devices");
    expect(call?.url).not.toContain("tok");
    expect((call?.init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });
});

describe("formatDowntime", () => {
  it("formata segundos, minutos e horas", () => {
    expect(formatDowntime(45)).toBe("45 s");
    expect(formatDowntime(190)).toBe("3 min");
    expect(formatDowntime(3900)).toBe("1 h 5 min");
  });
});
