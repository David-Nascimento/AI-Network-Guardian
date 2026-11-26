// Espelha os schemas do backend (app/schemas). Mantenha em sincronia.

export type TargetKind = "gateway" | "external" | "dns";
export type TargetMethod = "icmp" | "tcp" | "dns";
export type ConnectivityState = "online" | "degraded" | "offline" | "unknown";

export interface Target {
  id: number;
  name: string;
  host: string;
  kind: TargetKind;
  method: TargetMethod;
  port: number | null;
  enabled: boolean;
  created_at: string;
}

export type TargetInput = Omit<Target, "id" | "created_at">;

export interface NetworkEvent {
  id: number;
  event_type: string;
  severity: "info" | "warning" | "critical";
  target_id: number | null;
  message: string;
  details: Record<string, unknown>;
  started_at: string;
  ended_at: string | null;
}

export interface TargetStatus {
  target: Target;
  down: boolean;
  last_sample_at: string | null;
  latency_avg_ms: number | null;
  packet_loss_pct: number | null;
}

export interface NetworkStatus {
  state: ConnectivityState;
  summary: string;
  checked_at: string;
  targets: TargetStatus[];
  active_events: NetworkEvent[];
}

export interface MetricPoint {
  ts: string;
  target_id: number;
  latency_avg_ms: number | null;
  latency_max_ms: number | null;
  jitter_ms: number | null;
  packet_loss_pct: number;
  samples: number;
}

export interface MetricsSummary {
  since: string;
  until: string;
  samples: number;
  availability_pct: number | null;
  latency_min_ms: number | null;
  latency_avg_ms: number | null;
  latency_max_ms: number | null;
  jitter_avg_ms: number | null;
  packet_loss_avg_pct: number | null;
}

export interface MetricsComparison {
  current: MetricsSummary;
  previous: MetricsSummary;
  latency_avg_delta_ms: number | null;
  packet_loss_delta_pct: number | null;
  availability_delta_pct: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  username: string;
  role: "admin" | "viewer";
}

export type DeviceCategory =
  | "unknown"
  | "computer"
  | "smartphone"
  | "tv"
  | "iot"
  | "network"
  | "printer"
  | "other";

export interface Device {
  id: number;
  mac: string;
  ip: string;
  hostname: string | null;
  vendor: string | null;
  custom_name: string | null;
  category: DeviceCategory;
  is_known: boolean;
  online: boolean;
  first_seen: string;
  last_seen: string;
  ports_scanned_at: string | null;
}

export interface DeviceEvent {
  id: number;
  event_type: string;
  detail: string | null;
  ts: string;
}

export interface ScanResult {
  network: string;
  found: number;
  new: number;
  reconnected: number;
  disconnected: number;
  scanned_at: string;
}

export interface TopologyNode {
  id: string;
  kind: "internet" | "gateway" | "device";
  label: string;
  status: "online" | "offline" | "unknown";
  category: string | null;
  ip: string | null;
  device_id: number | null;
  is_known: boolean | null;
}

export interface TopologyEdge {
  source: string;
  target: string;
  confidence: "confirmed" | "inferred";
  reason: string;
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  notes: string[];
}

export interface PortInfo {
  port: number;
  service: string;
  first_seen: string;
  last_seen: string;
}

export interface PortScanResult {
  scanned_at: string;
  checked: number;
  open_ports: PortInfo[];
}

export interface ImportNamesResult {
  parsed: number;
  matched: number;
  updated: number;
}

export type AlertSeverity = "info" | "warning" | "critical";
export type AlertStatus = "new" | "acknowledged" | "resolved";
export type AlertFilter = "active" | "new" | "acknowledged" | "resolved" | "all";

export interface Alert {
  id: number;
  kind: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  device_id: number | null;
  created_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  status: AlertStatus;
}

export interface AlertSummary {
  new: number;
  acknowledged: number;
  critical_active: number;
}

export interface AlertRule {
  kind: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface LiveEvent {
  type: string;
  data: Record<string, unknown>;
  ts: string | null;
}

export interface Anomaly {
  id: number;
  target_id: number;
  window_start: string;
  method: string;
  score: number;
  features: Record<string, number>;
  deviations: string[];
}

export interface MlTargetStatus {
  target_id: number;
  name: string;
  windows: number;
  ready: boolean;
}

export interface MlStatus {
  enabled: boolean;
  configured_method: string;
  effective_method: string | null;
  sklearn_available: boolean;
  window_minutes: number;
  min_windows: number;
  train_hours: number;
  targets: MlTargetStatus[];
}

export interface AgentStatus {
  enabled: boolean;
  model: string | null;
  reachable: boolean;
  model_installed: boolean;
  detail: string | null;
  tools: string[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ToolTrace {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string;
}

export interface ChatResponse {
  answer: string;
  stopped: "answered" | "max_steps";
  steps: number;
  tool_calls: ToolTrace[];
}

export interface TargetReport {
  target_id: number;
  name: string;
  availability_pct: number | null;
  latency_avg_ms: number | null;
  packet_loss_avg_pct: number | null;
  samples: number;
}

export interface ReportSummary {
  generated_at: string;
  since: string;
  until: string;
  hours: number;
  availability_pct: number | null;
  latency_avg_ms: number | null;
  latency_max_ms: number | null;
  jitter_avg_ms: number | null;
  packet_loss_avg_pct: number | null;
  samples: number;
  targets: TargetReport[];
  incidents: { count: number; downtime_seconds: number; by_type: Record<string, number> };
  devices: { total: number; online: number; known: number; unknown: number; first_seen_in_period: number };
  alerts: { created: number; by_kind: Record<string, number>; still_active: number };
  anomalies: number;
  notes: string[];
}

export type ExportKind = "metrics" | "events" | "devices" | "alerts";
