import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "@/components/ui/states";
import type { MetricPoint, Target } from "@/types/api";
import { formatClock, formatMs, formatPct, pivotMetric, type MetricField } from "@/utils/format";

const COLORS = ["#22d3ee", "#34d399", "#fbbf24", "#60a5fa", "#f97316", "#94a3b8"];

const FORMAT: Record<MetricField, (v: number | null) => string> = {
  latency_avg_ms: formatMs,
  jitter_ms: formatMs,
  packet_loss_pct: formatPct,
};

export function MetricChart({
  points,
  targets,
  metric,
  label,
  unit,
  height = 260,
}: {
  points: MetricPoint[];
  targets: Pick<Target, "id" | "name">[];
  metric: MetricField;
  label: string;
  unit: string;
  height?: number;
}) {
  const data = pivotMetric(points, targets, metric);
  if (data.length === 0) {
    return (
      <EmptyState
        title="Sem medições no período"
        hint="O gráfico aparece depois do primeiro ciclo de coleta."
      />
    );
  }
  const series = targets.filter((t) => data.some((row) => row[t.name] != null));
  return (
    <div role="img" aria-label={label} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.12} />
          <XAxis dataKey="ts" tickFormatter={formatClock} tick={{ fontSize: 11 }} minTickGap={40} />
          <YAxis tick={{ fontSize: 11 }} unit={unit} />
          <Tooltip
            labelFormatter={(v) => formatClock(String(v))}
            formatter={(v) => FORMAT[metric](typeof v === "number" ? v : null)}
            contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((t, i) => (
            <Line
              key={t.id}
              type="monotone"
              dataKey={t.name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
