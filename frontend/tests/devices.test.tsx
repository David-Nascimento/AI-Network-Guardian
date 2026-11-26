import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Devices } from "@/pages/Devices";
import { toFlow } from "@/pages/Topology";
import { authStore } from "@/stores/auth";
import type { Device, Topology } from "@/types/api";
import { layoutTopology } from "@/utils/topology";
import { mockFetch, renderApp } from "./helpers";

const device = (over: Partial<Device> = {}): Device => ({
  id: 1,
  mac: "f4:b5:20:00:00:01",
  ip: "192.168.0.10",
  hostname: "notebook",
  vendor: null,
  custom_name: null,
  category: "unknown",
  is_known: false,
  online: true,
  first_seen: "2026-11-25T10:00:00Z",
  last_seen: "2026-11-25T11:00:00Z",
  ports_scanned_at: null,
  ...over,
});

const me = (role: string) => ({ "GET /api/v1/auth/me": { body: { id: 1, username: "u", role } } });

beforeEach(() => authStore.setToken("tok"));

describe("Devices", () => {
  it("lista dispositivos, mostra fabricante desconhecido e não presume malícia", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/devices": { body: [device(), device({ id: 2, ip: "192.168.0.11", mac: "aa:bb:cc:00:00:02", online: false, is_known: true })] },
    });
    renderApp(<Devices />);
    expect(await screen.findByText("192.168.0.10")).toBeInTheDocument();
    expect(screen.getAllByText("desconhecido").length).toBeGreaterThan(0);
    expect(screen.getByText(/não significa malicioso/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /varrer agora/i })).not.toBeInTheDocument();
  });

  it("filtra por status", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/devices": { body: [device(), device({ id: 2, ip: "192.168.0.11", mac: "aa:bb:cc:00:00:02", online: false })] },
    });
    renderApp(<Devices />);
    await screen.findByText("192.168.0.10");
    await userEvent.selectOptions(screen.getByLabelText("Filtrar por status"), "offline");
    expect(screen.queryByText("192.168.0.10")).not.toBeInTheDocument();
    expect(screen.getByText("192.168.0.11")).toBeInTheDocument();
  });

  it("admin varre e vê o resultado", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/devices": { body: [device()] },
      "POST /api/v1/devices/scan": {
        body: { network: "192.168.0.0/24", found: 3, new: 1, reconnected: 0, disconnected: 0, scanned_at: "2026-11-25T11:00:00Z" },
      },
    });
    renderApp(<Devices />);
    await userEvent.click(await screen.findByRole("button", { name: /varrer agora/i }));
    expect(await screen.findByRole("status")).toHaveTextContent("192.168.0.0/24: 3 encontrados");
    expect(calls.some((c) => c.key === "POST /api/v1/devices/scan")).toBe(true);
  });

  it("admin renomeia e mostra erro da API", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/devices": { body: [device()] },
      "PATCH /api/v1/devices/1": { body: device({ custom_name: "Sala" }) },
    });
    renderApp(<Devices />);
    const input = await screen.findByLabelText("Nome de 192.168.0.10");
    await userEvent.type(input, "Sala");
    await userEvent.tab();
    await waitFor(() => expect(calls.some((c) => c.key === "PATCH /api/v1/devices/1")).toBe(true));
    const patch = calls.find((c) => c.key === "PATCH /api/v1/devices/1");
    expect(JSON.parse(String(patch?.init?.body))).toEqual({ custom_name: "Sala" });
  });

  it("marcar todos pede confirmação", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = mockFetch({ ...me("admin"), "GET /api/v1/devices": { body: [device()] } });
    renderApp(<Devices />);
    await userEvent.click(await screen.findByRole("button", { name: /marcar todos/i }));
    expect(confirm).toHaveBeenCalled();
    expect(calls.some((c) => c.key.startsWith("POST"))).toBe(false);
  });

  it("expande o histórico", async () => {
    mockFetch({
      ...me("viewer"),
      "GET /api/v1/devices": { body: [device()] },
      "GET /api/v1/devices/1/events": { body: [{ id: 1, event_type: "connected", detail: null, ts: "2026-11-25T10:00:00Z" }] },
      "GET /api/v1/devices/1/ports": { body: [] },
    });
    renderApp(<Devices />);
    await userEvent.click(await screen.findByRole("button", { name: /histórico/i }));
    expect(await screen.findByText("Conectou")).toBeInTheDocument();
  });

  it("admin escaneia portas e vê os serviços", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/devices": { body: [device()] },
      "GET /api/v1/devices/1/events": { body: [] },
      "GET /api/v1/devices/1/ports": { body: [] },
      "POST /api/v1/devices/1/ports/scan": {
        body: { scanned_at: "2026-11-25T12:00:00Z", checked: 20, open_ports: [{ port: 80, service: "HTTP", first_seen: "2026-11-25T12:00:00Z", last_seen: "2026-11-25T12:00:00Z" }] },
      },
    });
    renderApp(<Devices />);
    await userEvent.click(await screen.findByRole("button", { name: /histórico/i }));
    expect(await screen.findByText("Ainda não escaneado.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /escanear portas/i }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/v1/devices/1/ports/scan")).toBe(true));
    expect(screen.getByText(/porta aberta não é falha/i)).toBeInTheDocument();
  });

  it("importa nomes colados do roteador", async () => {
    const { calls } = mockFetch({
      ...me("admin"),
      "GET /api/v1/devices": { body: [device()] },
      "POST /api/v1/devices/import-names": { body: { parsed: 3, matched: 2, updated: 2 } },
    });
    renderApp(<Devices />);
    await userEvent.click(await screen.findByRole("button", { name: /importar nomes do roteador/i }));
    const box = screen.getByLabelText("Tabela do roteador");
    await userEvent.click(box);
    await userEvent.paste("iPhone\t192.168.0.10\taa:bb:cc:dd:ee:ff");
    await userEvent.click(screen.getByRole("button", { name: "Importar" }));
    expect(await screen.findByRole("status")).toHaveTextContent("2 nomes atualizados");
    const post = calls.find((c) => c.key === "POST /api/v1/devices/import-names");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ text: "iPhone\t192.168.0.10\taa:bb:cc:dd:ee:ff" });
  });

  it("estado vazio", async () => {
    mockFetch({ ...me("viewer"), "GET /api/v1/devices": { body: [] } });
    renderApp(<Devices />);
    expect(await screen.findByText(/nenhum dispositivo descoberto/i)).toBeInTheDocument();
  });
});

const topo: Topology = {
  nodes: [
    { id: "internet", kind: "internet", label: "Internet", status: "online", category: null, ip: null, device_id: null, is_known: null },
    { id: "gateway", kind: "gateway", label: "Gateway", status: "online", category: null, ip: "192.168.0.1", device_id: null, is_known: null },
    { id: "d1", kind: "device", label: "A", status: "online", category: "unknown", ip: "192.168.0.10", device_id: 1, is_known: false },
    { id: "d2", kind: "device", label: "B", status: "offline", category: "tv", ip: "192.168.0.11", device_id: 2, is_known: true },
  ],
  edges: [
    { source: "internet", target: "gateway", confidence: "confirmed", reason: "ok" },
    { source: "gateway", target: "d1", confidence: "inferred", reason: "L3" },
  ],
  notes: [],
};

describe("topologia", () => {
  it("posiciona internet acima do gateway e dispositivos abaixo", () => {
    const all = new Map(layoutTopology(topo.nodes).map((p) => [p.id, p]));
    const at = (id: string) => all.get(id) ?? { id, x: NaN, y: NaN };
    const pos = { internet: at("internet"), gateway: at("gateway"), d1: at("d1"), d2: at("d2") };
    expect(pos.internet.y).toBeLessThan(pos.gateway.y);
    expect(pos.gateway.y).toBeLessThan(pos.d1.y);
    expect(pos.d1.x).not.toBe(pos.d2.x);
    expect(pos.internet.x).toBe(pos.gateway.x);
  });

  it("arestas inferidas são tracejadas e confirmadas são sólidas", () => {
    const { edges, nodes } = toFlow(topo);
    expect(nodes).toHaveLength(4);
    expect(edges.find((e) => e.target === "gateway")?.style?.strokeDasharray).toBeUndefined();
    expect(edges.find((e) => e.target === "d1")?.style?.strokeDasharray).toBeDefined();
  });
});

describe("rótulo dos nós", () => {
  it("não repete o IP quando o nó não tem nome", () => {
    const { nodes } = toFlow({
      nodes: [{ id: "d1", kind: "device", label: "192.168.0.10", status: "online", category: null, ip: "192.168.0.10", device_id: 1, is_known: false }],
      edges: [],
      notes: [],
    });
    expect((nodes[0]?.data as { label: string }).label).toBe("192.168.0.10");
  });
});
