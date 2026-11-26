import { useState } from "react";

import { LatencyChart } from "@/components/charts/LatencyChart";
import { MetricChart } from "@/components/charts/MetricChart";
import { EventList } from "@/components/network/EventList";
import { deltaLabel, StatCard } from "@/components/network/StatCard";
import { TargetsPanel } from "@/components/network/TargetsPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/hooks/useAuth";
import { useComparison, useEvents, useHistory, useNetworkStatus } from "@/hooks/useNetwork";
import { cn } from "@/utils/cn";
import { formatMs, formatPct, PERIODS } from "@/utils/format";

export function NetworkMonitor() {
  const [periodIndex, setPeriodIndex] = useState(2);
  const [targetId, setTargetId] = useState<number | undefined>(undefined);
  const period = PERIODS[periodIndex] ?? PERIODS[2];

  const { data: me } = useMe();
  const status = useNetworkStatus();
  const history = useHistory(period.hours, period.bucket, targetId);
  const comparison = useComparison(period.hours, targetId);
  const events = useEvents(period.hours);

  const allTargets = status.data?.targets.map((t) => t.target) ?? [];
  const charted = targetId ? allTargets.filter((t) => t.id === targetId) : allTargets;
  const cur = comparison.data?.current;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Network Monitor</h1>
          <p className="text-sm text-muted-foreground">
            Latência, jitter, perda e disponibilidade por destino · atualização automática
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label="Filtrar por destino" className="w-48" value={targetId ?? ""}
            onChange={(e) => setTargetId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">Todos os destinos</option>
            {allTargets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
          <div role="group" aria-label="Período" className="flex gap-1">
            {PERIODS.map((p, i) => (
              <Button key={p.hours} size="sm" variant={i === periodIndex ? "primary" : "outline"}
                aria-pressed={i === periodIndex} onClick={() => setPeriodIndex(i)}>
                {p.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {comparison.isError ? (
        <ErrorState error={comparison.error} onRetry={() => void comparison.refetch()} />
      ) : (
        <section aria-label="Resumo do período" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard title="Latência média" value={formatMs(cur?.latency_avg_ms)} loading={comparison.isLoading}
            hint={cur && deltaLabel(comparison.data?.latency_avg_delta_ms ?? null, " ms", true)} className="text-network" />
          <StatCard title="Mín / máx" value={`${formatMs(cur?.latency_min_ms)} / ${formatMs(cur?.latency_max_ms)}`}
            loading={comparison.isLoading} hint={`jitter médio ${formatMs(cur?.jitter_avg_ms)}`} className="text-network text-xl" />
          <StatCard title="Perda de pacotes" value={formatPct(cur?.packet_loss_avg_pct)} loading={comparison.isLoading}
            hint={cur && deltaLabel(comparison.data?.packet_loss_delta_pct ?? null, " p.p.", true)}
            className={cn((cur?.packet_loss_avg_pct ?? 0) >= 10 ? "text-warning" : "text-success")} />
          <StatCard title="Disponibilidade" value={formatPct(cur?.availability_pct)} loading={comparison.isLoading}
            hint={cur && deltaLabel(comparison.data?.availability_delta_pct ?? null, " p.p.", false)} className="text-success" />
        </section>
      )}

      <Card>
        <CardHeader><CardTitle>Latência no período</CardTitle></CardHeader>
        <CardContent>
          {history.isError ? <ErrorState error={history.error} onRetry={() => void history.refetch()} />
            : history.isLoading ? <Skeleton className="h-64 w-full" />
            : <LatencyChart points={history.data ?? []} targets={charted} />}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Jitter no período</CardTitle></CardHeader>
          <CardContent>
            {history.isLoading ? <Skeleton className="h-52 w-full" />
              : <MetricChart points={history.data ?? []} targets={charted} metric="jitter_ms"
                  label="Gráfico de jitter por destino" unit=" ms" height={220} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Perda de pacotes no período</CardTitle></CardHeader>
          <CardContent>
            {history.isLoading ? <Skeleton className="h-52 w-full" />
              : <MetricChart points={history.data ?? []} targets={charted} metric="packet_loss_pct"
                  label="Gráfico de perda de pacotes por destino" unit="%" height={220} />}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Interrupções no período</CardTitle></CardHeader>
        <CardContent>
          {events.isError ? <ErrorState error={events.error} onRetry={() => void events.refetch()} />
            : events.isLoading ? <Skeleton className="h-20 w-full" />
            : <EventList events={events.data ?? []} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Destinos monitorados</CardTitle></CardHeader>
        <CardContent><TargetsPanel isAdmin={me?.role === "admin"} /></CardContent>
      </Card>
    </>
  );
}
