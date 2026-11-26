import { describe, expect, it } from "vitest";

import type { MetricPoint } from "@/types/api";
import { EMPTY, formatDuration, formatMs, formatPct, pivotLatency } from "@/utils/format";

const point = (ts: string, target_id: number, latency: number | null): MetricPoint => ({
  ts,
  target_id,
  latency_avg_ms: latency,
  latency_max_ms: latency,
  jitter_ms: null,
  packet_loss_pct: 0,
  samples: 1,
});

describe("formatadores", () => {
  it("formata latência e trata ausência de dados", () => {
    expect(formatMs(4.26)).toBe("4.3 ms");
    expect(formatMs(45.4)).toBe("45 ms");
    expect(formatMs(null)).toBe(EMPTY);
    expect(formatMs(undefined)).toBe(EMPTY);
  });

  it("formata porcentagem", () => {
    expect(formatPct(0)).toBe("0%");
    expect(formatPct(100)).toBe("100%");
    expect(formatPct(12.34)).toBe("12.3%");
    expect(formatPct(null)).toBe(EMPTY);
  });

  it("formata duração", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:30Z")).toBe("30s");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z")).toBe("5 min");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T02:10:00Z")).toBe("2 h 10 min");
  });
});

describe("pivotLatency", () => {
  const targets = [
    { id: 1, name: "A" },
    { id: 2, name: "B" },
  ];

  it("junta destinos por instante e ordena no tempo", () => {
    const rows = pivotLatency(
      [point("2026-01-01T00:15:00Z", 1, 20), point("2026-01-01T00:00:00Z", 1, 10), point("2026-01-01T00:00:00Z", 2, 30)],
      targets,
    );
    expect(rows).toEqual([
      { ts: "2026-01-01T00:00:00Z", A: 10, B: 30 },
      { ts: "2026-01-01T00:15:00Z", A: 20 },
    ]);
  });

  it("ignora destinos desconhecidos e preserva null", () => {
    const rows = pivotLatency([point("t", 9, 1), point("t", 1, null)], targets);
    expect(rows).toEqual([{ ts: "t", A: null }]);
  });
});
