import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { StatCard } from "@/components/network/StatCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/states";
import { api } from "@/services/api";
import type { ExportKind } from "@/types/api";
import { formatDateTime, formatMs, formatPct } from "@/utils/format";

const PERIODS = [
  { hours: 24, label: "Últimas 24 h" },
  { hours: 168, label: "Últimos 7 dias" },
  { hours: 720, label: "Últimos 30 dias" },
];

const EXPORTS: { kind: ExportKind; label: string }[] = [
  { kind: "metrics", label: "Medições (CSV)" },
  { kind: "events", label: "Quedas (CSV)" },
  { kind: "devices", label: "Dispositivos (CSV)" },
  { kind: "alerts", label: "Alertas (CSV)" },
];

export function formatDowntime(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  const m = Math.floor(seconds / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function Reports() {
  const [hours, setHours] = useState(24);
  const report = useQuery({ queryKey: ["report", hours], queryFn: () => api.reportSummary(hours) });
  const exporter = useMutation({
    mutationFn: async (kind: ExportKind) => {
      const { blob, filename } = await api.exportCsv(kind, hours);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
  const r = report.data;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Relatórios</h1>
          <p className="text-sm text-muted-foreground">Resumo do período com dados medidos; nada é estimado.</p>
        </div>
        <Select aria-label="Período do relatório" className="w-48" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
          {PERIODS.map((p) => (
            <option key={p.hours} value={p.hours}>
              {p.label}
            </option>
          ))}
        </Select>
      </div>

      {report.isError ? (
        <ErrorState error={report.error} onRetry={() => void report.refetch()} />
      ) : (
        <>
          <section aria-label="Indicadores do período" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard title="Disponibilidade" value={formatPct(r?.availability_pct)} loading={report.isLoading} className="text-success" />
            <StatCard title="Latência média" value={formatMs(r?.latency_avg_ms)} loading={report.isLoading}
              hint={r && `máx ${formatMs(r.latency_max_ms)} · jitter ${formatMs(r.jitter_avg_ms)}`} className="text-network" />
            <StatCard title="Perda de pacotes" value={formatPct(r?.packet_loss_avg_pct)} loading={report.isLoading} className="text-success" />
            <StatCard title="Quedas" value={String(r?.incidents.count ?? "—")} loading={report.isLoading}
              hint={r && `tempo total: ${formatDowntime(r.incidents.downtime_seconds)}`} className="text-warning" />
          </section>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader><CardTitle>Dispositivos (agora)</CardTitle></CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{r?.devices.total ?? "—"} no inventário · {r?.devices.online ?? "—"} online</p>
                <p>{r?.devices.known ?? "—"} reconhecidos · {r?.devices.unknown ?? "—"} ainda não reconhecidos</p>
                <p className="text-xs text-muted-foreground">{r?.devices.first_seen_in_period ?? "—"} apareceram pela 1ª vez no período</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Alertas no período</CardTitle></CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>{r?.alerts.created ?? "—"} gerados · {r?.alerts.still_active ?? "—"} ainda ativos</p>
                <p className="text-xs text-muted-foreground">
                  {Object.entries(r?.alerts.by_kind ?? {}).map(([k, n]) => `${k}: ${n}`).join(" · ") || "nenhum"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Comportamento fora do padrão</CardTitle></CardHeader>
              <CardContent className="text-sm">{r?.anomalies ?? "—"} janela(s) marcada(s) no período</CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle>Por destino</CardTitle></CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted-foreground">
                    <tr><th className="py-1 pr-4">Destino</th><th className="pr-4">Disponibilidade</th><th className="pr-4">Latência média</th><th className="pr-4">Perda</th><th>Amostras</th></tr>
                  </thead>
                  <tbody>
                    {(r?.targets ?? []).map((t) => (
                      <tr key={t.target_id} className="border-t border-border">
                        <td className="py-1.5 pr-4 font-medium">{t.name}</td>
                        <td className="pr-4">{formatPct(t.availability_pct)}</td>
                        <td className="pr-4">{formatMs(t.latency_avg_ms)}</td>
                        <td className="pr-4">{formatPct(t.packet_loss_avg_pct)}</td>
                        <td>{t.samples}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      <Card>
        <CardHeader><CardTitle>Exportar</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {EXPORTS.map((e) => (
              <Button key={e.kind} variant="outline" size="sm" disabled={exporter.isPending} onClick={() => exporter.mutate(e.kind)}>
                {e.label}
              </Button>
            ))}
          </div>
          {exporter.isError && <p role="alert" className="text-sm text-danger">Não foi possível exportar.</p>}
          <p className="text-xs text-muted-foreground">
            {r ? `Gerado em ${formatDateTime(r.generated_at)}. ` : ""}Horários em UTC nos arquivos CSV.
          </p>
          {r?.notes.map((n) => <p key={n} className="text-xs text-muted-foreground">{n}</p>)}
        </CardContent>
      </Card>
    </>
  );
}
