import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { LatencyChart } from "@/components/charts/LatencyChart";
import { EventList } from "@/components/network/EventList";
import { StatCard } from "@/components/network/StatCard";
import { StatusBadge } from "@/components/network/StatusBadge";
import { useEvents, useHistory, useNetworkStatus, useSummary } from "@/hooks/useNetwork";
import { formatClock, formatMs, formatPct } from "@/utils/format";

const HOURS = 24;
const BUCKET_MINUTES = 15;

export function Dashboard() {
  const status = useNetworkStatus();
  const summary = useSummary(HOURS);
  const history = useHistory(HOURS, BUCKET_MINUTES);
  const events = useEvents(HOURS);

  if (status.isError) return <ErrorState error={status.error} onRetry={() => void status.refetch()} />;

  const s = summary.data;
  const targets = status.data?.targets.map((t) => t.target) ?? [];
  const active = status.data?.active_events.length ?? 0;

  return (
    <>
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Medições reais dos destinos configurados · últimas {HOURS} h · atualização automática
          {status.data && ` · verificado às ${formatClock(status.data.checked_at)}`}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Status da internet</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          {status.isLoading ? (
            <Skeleton className="h-6 w-64" />
          ) : (
            <>
              <StatusBadge state={status.data?.state ?? "unknown"} />
              <span className="text-sm">{status.data?.summary}</span>
            </>
          )}
        </CardContent>
      </Card>

      <section aria-label="Indicadores" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard title="Latência média" value={formatMs(s?.latency_avg_ms)} loading={summary.isLoading}
          hint={`mín ${formatMs(s?.latency_min_ms)} · máx ${formatMs(s?.latency_max_ms)}`} className="text-network" />
        <StatCard title="Jitter" value={formatMs(s?.jitter_avg_ms)} loading={summary.isLoading} className="text-network" />
        <StatCard title="Perda de pacotes" value={formatPct(s?.packet_loss_avg_pct)} loading={summary.isLoading}
          className={(s?.packet_loss_avg_pct ?? 0) >= 10 ? "text-warning" : "text-success"} />
        <StatCard title="Disponibilidade" value={formatPct(s?.availability_pct)} loading={summary.isLoading}
          hint={s ? `${s.samples} medições` : undefined} className="text-success" />
        <StatCard title="Incidentes ativos" value={active} loading={status.isLoading}
          className={active > 0 ? "text-danger" : "text-success"} />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Latência por destino</CardTitle>
        </CardHeader>
        <CardContent>
          {history.isError ? (
            <ErrorState error={history.error} onRetry={() => void history.refetch()} />
          ) : history.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <LatencyChart points={history.data ?? []} targets={targets} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Eventos recentes</CardTitle>
        </CardHeader>
        <CardContent>
          {events.isError ? (
            <ErrorState error={events.error} onRetry={() => void events.refetch()} />
          ) : events.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <EventList events={events.data ?? []} limit={5} />
          )}
        </CardContent>
      </Card>
    </>
  );
}
