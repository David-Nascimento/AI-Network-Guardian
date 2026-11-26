import { CheckCircle2, CircleHelp, TriangleAlert, XCircle } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { ConnectivityState } from "@/types/api";
import { STATE_LABEL } from "@/utils/format";

const TONE: Record<ConnectivityState, BadgeTone> = {
  online: "success",
  degraded: "warning",
  offline: "danger",
  unknown: "neutral",
};

const ICON = {
  online: CheckCircle2,
  degraded: TriangleAlert,
  offline: XCircle,
  unknown: CircleHelp,
} as const;

export function StatusBadge({ state }: { state: ConnectivityState }) {
  const Icon = ICON[state];
  return (
    <Badge tone={TONE[state]}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {STATE_LABEL[state]}
    </Badge>
  );
}
