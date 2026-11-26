import { Badge, type BadgeTone } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import type { NetworkEvent } from "@/types/api";
import { EVENT_LABEL, formatDateTime, formatDuration } from "@/utils/format";

const SEVERITY: Record<NetworkEvent["severity"], { tone: BadgeTone; label: string }> = {
  info: { tone: "network", label: "Info" },
  warning: { tone: "warning", label: "Atenção" },
  critical: { tone: "danger", label: "Crítico" },
};

export function EventList({ events, limit }: { events: NetworkEvent[]; limit?: number }) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="Nenhuma interrupção no período"
        hint="Eventos aparecem aqui quando um destino ou a internet ficam indisponíveis."
      />
    );
  }
  return (
    <ul className="divide-y divide-border">
      {events.slice(0, limit).map((e) => (
        <li key={e.id} className="flex flex-col gap-1 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={SEVERITY[e.severity].tone}>{SEVERITY[e.severity].label}</Badge>
            <span className="font-medium">{EVENT_LABEL[e.event_type] ?? e.event_type}</span>
            <span className="text-xs text-muted-foreground">
              {formatDateTime(e.started_at)} ·{" "}
              {e.ended_at ? `durou ${formatDuration(e.started_at, e.ended_at)}` : "em andamento"}
            </span>
          </div>
          <p className="text-muted-foreground">{e.message}</p>
        </li>
      ))}
    </ul>
  );
}
