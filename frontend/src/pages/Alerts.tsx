import { useState } from "react";

import { AnomalyCard } from "@/components/network/AnomalyCard";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useMe } from "@/hooks/useAuth";
import { useAlertMutations, useAlertRules, useAlerts } from "@/hooks/useAlerts";
import type { Alert, AlertFilter, AlertSeverity, AlertStatus } from "@/types/api";
import { formatDateTime } from "@/utils/format";

const SEVERITY: Record<AlertSeverity, { label: string; tone: BadgeTone }> = {
  info: { label: "Informação", tone: "network" },
  warning: { label: "Atenção", tone: "warning" },
  critical: { label: "Crítico", tone: "danger" },
};

const STATUS: Record<AlertStatus, { label: string; tone: BadgeTone }> = {
  new: { label: "Novo", tone: "warning" },
  acknowledged: { label: "Reconhecido", tone: "neutral" },
  resolved: { label: "Resolvido", tone: "success" },
};

const FILTERS: { value: AlertFilter; label: string }[] = [
  { value: "active", label: "Ativos" },
  { value: "new", label: "Novos" },
  { value: "acknowledged", label: "Reconhecidos" },
  { value: "resolved", label: "Resolvidos" },
  { value: "all", label: "Todos" },
];

function AlertRow({ alert, isAdmin, onAck, busy }: { alert: Alert; isAdmin: boolean; onAck: () => void; busy: boolean }) {
  const sev = SEVERITY[alert.severity];
  const st = STATUS[alert.status];
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 border-b border-border py-3 last:border-0">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={sev.tone}>{sev.label}</Badge>
          <Badge tone={st.tone}>{st.label}</Badge>
          <span className="text-sm font-medium">{alert.title}</span>
        </div>
        <p className="text-sm text-muted-foreground">{alert.message}</p>
        <p className="text-xs text-muted-foreground">
          {formatDateTime(alert.created_at)}
          {alert.resolved_at && ` · resolvido em ${formatDateTime(alert.resolved_at)}`}
          {alert.acknowledged_by && ` · reconhecido por ${alert.acknowledged_by}`}
        </p>
      </div>
      {isAdmin && alert.status === "new" && (
        <Button size="sm" variant="outline" disabled={busy} onClick={onAck} aria-label={`Reconhecer alerta: ${alert.title}`}>
          Reconhecer
        </Button>
      )}
    </li>
  );
}

function RulesCard({ isAdmin }: { isAdmin: boolean }) {
  const rules = useAlertRules();
  const { setRule } = useAlertMutations();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Quais alertas gerar</CardTitle>
      </CardHeader>
      <CardContent>
        {rules.isError ? (
          <ErrorState error={rules.error} onRetry={() => void rules.refetch()} />
        ) : rules.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <ul className="space-y-3">
            {(rules.data ?? []).map((r) => (
              <li key={r.kind} className="flex items-start gap-3">
                <input
                  id={`rule-${r.kind}`}
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={r.enabled}
                  disabled={!isAdmin || setRule.isPending}
                  onChange={(e) => setRule.mutate({ kind: r.kind, enabled: e.target.checked })}
                />
                <label htmlFor={`rule-${r.kind}`} className="text-sm">
                  <span className="font-medium">{r.label}</span>
                  <span className="block text-xs text-muted-foreground">{r.description}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
        {!isAdmin && <p className="mt-3 text-xs text-muted-foreground">Somente administradores alteram as regras.</p>}
      </CardContent>
    </Card>
  );
}

export function Alerts() {
  const [filter, setFilter] = useState<AlertFilter>("active");
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";
  const alerts = useAlerts(filter);
  const { ack, ackAll } = useAlertMutations();
  const items = alerts.data ?? [];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Alertas</h1>
          <p className="text-sm text-muted-foreground">
            Gerados a partir de medições e varreduras reais · resolvem sozinhos quando a condição passa
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label="Filtrar alertas" className="w-44" value={filter} onChange={(e) => setFilter(e.target.value as AlertFilter)}>
            {FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
          {isAdmin && (
            <Button variant="outline" disabled={ackAll.isPending} onClick={() => ackAll.mutate()}>
              Reconhecer todos
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardContent className="pt-4">
          {alerts.isError ? (
            <ErrorState error={alerts.error} onRetry={() => void alerts.refetch()} />
          ) : alerts.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : items.length === 0 ? (
            <EmptyState title="Nenhum alerta neste filtro" hint="Quando algo relevante acontecer na rede, aparece aqui." />
          ) : (
            <ul aria-label="Lista de alertas">
              {items.map((a) => (
                <AlertRow key={a.id} alert={a} isAdmin={isAdmin} busy={ack.isPending} onAck={() => ack.mutate(a.id)} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <AnomalyCard />

      <RulesCard isAdmin={isAdmin} />
    </>
  );
}
