import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { authStore, useToken } from "@/stores/auth";
import { liveStore } from "@/stores/live";
import type { LiveEvent } from "@/types/api";

const RETRY_MIN_MS = 1_000;
const RETRY_MAX_MS = 30_000;

/** Quais consultas ficam velhas quando cada tipo de evento chega. */
export function invalidateFor(qc: QueryClient, event: LiveEvent): void {
  const keys: string[][] = [];
  switch (event.type) {
    case "network.updated":
      keys.push(["network"], ["metrics"], ["topology"], ["alerts"]);
      break;
    case "devices.updated":
    case "device.event":
      keys.push(["devices"], ["topology"], ["alerts"]);
      break;
    case "anomalies.updated":
      keys.push(["ml"], ["alerts"]);
      break;
    case "alert.created":
    case "alert.updated":
      keys.push(["alerts"]);
      break;
    default:
      return; // evento desconhecido: ignora
  }
  for (const queryKey of keys) void qc.invalidateQueries({ queryKey });
}

export function liveUrl(loc: Pick<Location, "protocol" | "host"> = window.location): string {
  return `${loc.protocol === "https:" ? "wss" : "ws"}://${loc.host}/api/v1/ws`;
}

/**
 * Mantém um WebSocket autenticado enquanto houver sessão. O token vai na primeira
 * mensagem (não na URL). Se cair, reconecta com espera crescente; enquanto isso o
 * polling normal continua valendo (ver `pollMs`).
 */
export function useLiveEvents(): void {
  const qc = useQueryClient();
  const token = useToken();

  useEffect(() => {
    if (!token || typeof WebSocket === "undefined") {
      liveStore.set("offline");
      return;
    }
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = RETRY_MIN_MS;
    let stopped = false;

    const connect = () => {
      liveStore.set("connecting");
      socket = new WebSocket(liveUrl());
      socket.onopen = () => socket?.send(JSON.stringify({ type: "auth", token: authStore.getToken() }));
      socket.onmessage = (msg: MessageEvent<string>) => {
        let event: LiveEvent;
        try {
          event = JSON.parse(msg.data) as LiveEvent;
        } catch {
          return;
        }
        if (event.type === "ready") {
          delay = RETRY_MIN_MS;
          liveStore.set("live");
          void qc.invalidateQueries(); // recupera o que passou enquanto estava offline
          return;
        }
        invalidateFor(qc, event);
      };
      socket.onclose = (e: CloseEvent) => {
        liveStore.set("offline");
        if (stopped || e.code === 4401) return; // 4401: token inválido, não adianta insistir
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, RETRY_MAX_MS);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
      liveStore.set("offline");
    };
  }, [token, qc]);
}
