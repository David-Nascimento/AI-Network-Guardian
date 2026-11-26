import { authStore } from "@/stores/auth";
import type {
  AgentStatus,
  Alert,
  AlertFilter,
  AlertRule,
  AlertSummary,
  ChatResponse,
  ExportKind,
  ChatTurn,
  Anomaly,
  Device,
  DeviceEvent,
  ImportNamesResult,
  PortInfo,
  PortScanResult,
  MetricPoint,
  MetricsComparison,
  MetricsSummary,
  MlStatus,
  NetworkEvent,
  NetworkStatus,
  ReportSummary,
  ScanResult,
  Target,
  TargetInput,
  TokenResponse,
  Topology,
  User,
} from "@/types/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; query?: Query; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  const token = authStore.getToken();
  if (init.auth !== false && token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(withQuery(path, init.query), {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError("Não foi possível conectar ao servidor.", 0, "network_error");
  }

  if (response.status === 401 && init.auth !== false) authStore.clear();
  if (response.status === 204) return undefined as T;

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const err = (payload as { error?: { message?: string; code?: string } } | null)?.error;
    throw new ApiError(err?.message ?? `Erro ${response.status}`, response.status, err?.code);
  }
  return payload as T;
}

/** Baixa um arquivo autenticado (o token vai no cabeçalho, nunca na URL). */
async function download(path: string, query: Query): Promise<{ blob: Blob; filename: string }> {
  const token = authStore.getToken();
  let response: Response;
  try {
    response = await fetch(withQuery(path, query), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ApiError("Não foi possível conectar ao servidor.", 0, "network_error");
  }
  if (response.status === 401) authStore.clear();
  if (!response.ok) throw new ApiError(`Erro ${response.status}`, response.status);
  const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "");
  return { blob: await response.blob(), filename: match?.[1] ?? "relatorio.csv" };
}

const BASE = "/api/v1";

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>(`${BASE}/auth/login`, {
      method: "POST",
      body: { username, password },
      auth: false,
    }),
  me: () => request<User>(`${BASE}/auth/me`),
  networkStatus: () => request<NetworkStatus>(`${BASE}/network/status`),
  targets: () => request<Target[]>(`${BASE}/network/targets`),
  createTarget: (body: TargetInput) =>
    request<Target>(`${BASE}/network/targets`, { method: "POST", body }),
  updateTarget: (id: number, body: Partial<Pick<Target, "name" | "enabled">>) =>
    request<Target>(`${BASE}/network/targets/${id}`, { method: "PATCH", body }),
  deleteTarget: (id: number) =>
    request<void>(`${BASE}/network/targets/${id}`, { method: "DELETE" }),
  events: (query: { hours: number; active_only?: boolean }) =>
    request<NetworkEvent[]>(`${BASE}/network/events`, { query }),
  history: (query: { hours: number; target_id?: number; bucket_minutes?: number }) =>
    request<MetricPoint[]>(`${BASE}/metrics/history`, { query }),
  summary: (query: { hours: number; target_id?: number }) =>
    request<MetricsSummary>(`${BASE}/metrics/summary`, { query }),
  compare: (query: { hours: number; target_id?: number }) =>
    request<MetricsComparison>(`${BASE}/metrics/compare`, { query }),
  devices: () => request<Device[]>(`${BASE}/devices`),
  deviceEvents: (id: number) => request<DeviceEvent[]>(`${BASE}/devices/${id}/events`),
  updateDevice: (
    id: number,
    body: Partial<Pick<Device, "custom_name" | "category" | "is_known">>,
  ) => request<Device>(`${BASE}/devices/${id}`, { method: "PATCH", body }),
  scanDevices: () => request<ScanResult>(`${BASE}/devices/scan`, { method: "POST" }),
  markAllKnown: () =>
    request<{ updated: number }>(`${BASE}/devices/mark-all-known`, { method: "POST" }),
  devicePorts: (id: number) => request<PortInfo[]>(`${BASE}/devices/${id}/ports`),
  scanPorts: (id: number) =>
    request<PortScanResult>(`${BASE}/devices/${id}/ports/scan`, { method: "POST" }),
  importNames: (text: string) =>
    request<ImportNamesResult>(`${BASE}/devices/import-names`, { method: "POST", body: { text } }),
  topology: () => request<Topology>(`${BASE}/topology`),
  reportSummary: (hours: number) => request<ReportSummary>(`${BASE}/reports/summary`, { query: { hours } }),
  exportCsv: (kind: ExportKind, hours: number) => download(`${BASE}/reports/export`, { kind, hours }),
  agentStatus: () => request<AgentStatus>(`${BASE}/agent/status`),
  agentChat: (message: string, history: ChatTurn[]) =>
    request<ChatResponse>(`${BASE}/agent/chat`, { method: "POST", body: { message, history } }),
  mlStatus: () => request<MlStatus>(`${BASE}/ml/status`),
  anomalies: (hours: number) => request<Anomaly[]>(`${BASE}/ml/anomalies`, { query: { hours } }),
  alerts: (status: AlertFilter) => request<Alert[]>(`${BASE}/alerts`, { query: { status } }),
  alertSummary: () => request<AlertSummary>(`${BASE}/alerts/summary`),
  alertRules: () => request<AlertRule[]>(`${BASE}/alerts/rules`),
  setAlertRule: (kind: string, enabled: boolean) =>
    request<AlertRule>(`${BASE}/alerts/rules/${kind}`, { method: "PATCH", body: { enabled } }),
  ackAlert: (id: number) => request<Alert>(`${BASE}/alerts/${id}/ack`, { method: "POST" }),
  ackAllAlerts: () => request<{ updated: number }>(`${BASE}/alerts/ack-all`, { method: "POST" }),
};
