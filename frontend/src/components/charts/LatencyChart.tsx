import type { MetricPoint, Target } from "@/types/api";
import { MetricChart } from "./MetricChart";

export function LatencyChart({
  points,
  targets,
  height,
}: {
  points: MetricPoint[];
  targets: Pick<Target, "id" | "name">[];
  height?: number;
}) {
  return (
    <MetricChart
      points={points}
      targets={targets}
      metric="latency_avg_ms"
      label="Gráfico de latência por destino"
      unit=" ms"
      height={height}
    />
  );
}
