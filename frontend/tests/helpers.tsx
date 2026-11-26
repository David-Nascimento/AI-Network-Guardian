import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

export interface MockResponse {
  status?: number;
  body?: unknown;
}
export type Handler = MockResponse | ((init: RequestInit | undefined, url: string) => MockResponse);

/** Substitui fetch: chave = "METHOD /caminho" (sem query string). Rotas não mapeadas falham o teste. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: { key: string; init?: RequestInit; url: string }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    calls.push({ key, init, url });
    const handler = routes[key];
    if (!handler) throw new Error(`fetch não mapeado: ${key}`);
    const { status = 200, body } = typeof handler === "function" ? handler(init, url) : handler;
    return new Response(status === 204 ? null : JSON.stringify(body ?? {}), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return { calls, fn };
}

export function renderApp(ui: ReactElement, route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export const target = (over: Record<string, unknown> = {}) => ({
  id: 1,
  name: "Cloudflare",
  host: "1.1.1.1",
  kind: "external",
  method: "icmp",
  port: null,
  enabled: true,
  created_at: "2026-11-25T10:00:00Z",
  ...over,
});
