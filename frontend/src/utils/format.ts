import type { ConnectivityState, MetricPoint, Target } from "@/types/api";

export const EMPTY = "—";

export function formatMs(value: number | null | undefined): string {
  return value == null ? EMPTY : `${value.toFixed(value < 10 ? 1 : 0)} ms`;
}

export function formatPct(value: number | null | undefined): string {
  return value == null ? EMPTY : `${value.toFixed(value === 100 || value === 0 ? 0 : 1)}%`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function formatDuration(startIso: string, endIso: string | null): string {
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startIso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

export const STATE_LABEL: Record<ConnectivityState, string> = {
  online: "Online",
  degraded: "Instável",
  offline: "Offline",
  unknown: "Sem dados",
};

export const EVENT_LABEL: Record<string, string> = {
  internet_down: "Queda da internet",
  gateway_down: "Gateway sem resposta",
  target_down: "Destino indisponível",
  dns_down: "Falha de DNS",
};

export interface ChartRow {
  ts: string;
  [series: string]: number | string | null;
}

export type MetricField = "latency_avg_ms" | "jitter_ms" | "packet_loss_pct";

/** Uma linha por instante, com uma coluna por destino (chave = nome do destino). */
export function pivotMetric(
  points: MetricPoint[],
  targets: Pick<Target, "id" | "name">[],
  field: MetricField,
): ChartRow[] {
  const names = new Map(targets.map((t) => [t.id, t.name]));
  const rows = new Map<string, ChartRow>();
  for (const p of points) {
    const name = names.get(p.target_id);
    if (!name) continue;
    const row = rows.get(p.ts) ?? { ts: p.ts };
    row[name] = p[field];
    rows.set(p.ts, row);
  }
  return [...rows.values()].sort((a, b) => a.ts.localeCompare(b.ts));
}

export function pivotLatency(points: MetricPoint[], targets: Pick<Target, "id" | "name">[]): ChartRow[] {
  return pivotMetric(points, targets, "latency_avg_ms");
}

export const PERIODS = [
  { label: "1 h", hours: 1, bucket: 1 },
  { label: "6 h", hours: 6, bucket: 5 },
  { label: "24 h", hours: 24, bucket: 15 },
  { label: "7 dias", hours: 168, bucket: 60 },
] as const;
