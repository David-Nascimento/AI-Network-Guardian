import { describe, expect, it } from "vitest";

import { api, ApiError } from "@/services/api";
import { authStore } from "@/stores/auth";
import { mockFetch } from "./helpers";

describe("cliente da API", () => {
  it("envia o token Bearer e serializa a query", async () => {
    authStore.setToken("abc");
    const { calls } = mockFetch({ "GET /api/v1/metrics/summary": { body: { samples: 3 } } });
    await api.summary({ hours: 24, target_id: undefined });
    const headers = calls[0]?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer abc");
    expect(calls[0]?.url).toBe("/api/v1/metrics/summary?hours=24");
  });

  it("converte erro do backend em ApiError e limpa a sessão no 401", async () => {
    authStore.setToken("expirado");
    mockFetch({
      "GET /api/v1/auth/me": { status: 401, body: { error: { code: "unauthorized", message: "Token inválido" } } },
    });
    const err = await api.me().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 401, code: "unauthorized", message: "Token inválido" });
    expect(authStore.getToken()).toBeNull();
  });

  it("não derruba a sessão quando o login falha com 401", async () => {
    authStore.setToken("valido");
    mockFetch({ "POST /api/v1/auth/login": { status: 401, body: { error: { code: "unauthorized", message: "x" } } } });
    await api.login("a", "b").catch(() => undefined);
    expect(authStore.getToken()).toBe("valido");
  });

  it("trata falha de rede com mensagem amigável", async () => {
    globalThis.fetch = (() => Promise.reject(new TypeError("fail"))) as typeof fetch;
    await expect(api.targets()).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("aceita 204 sem corpo", async () => {
    mockFetch({ "DELETE /api/v1/network/targets/5": { status: 204 } });
    await expect(api.deleteTarget(5)).resolves.toBeUndefined();
  });
});
