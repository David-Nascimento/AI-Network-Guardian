import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import type { AlertFilter } from "@/types/api";
import { pollMs } from "./useNetwork";

export function useAlerts(status: AlertFilter) {
  return useQuery({
    queryKey: ["alerts", "list", status],
    queryFn: () => api.alerts(status),
    refetchInterval: pollMs,
  });
}

export function useAlertSummary() {
  return useQuery({
    queryKey: ["alerts", "summary"],
    queryFn: api.alertSummary,
    refetchInterval: pollMs,
  });
}

export function useAlertRules() {
  return useQuery({ queryKey: ["alerts", "rules"], queryFn: api.alertRules });
}

export function useAlertMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["alerts"] });
  return {
    ack: useMutation({ mutationFn: (id: number) => api.ackAlert(id), onSuccess: refresh }),
    ackAll: useMutation({ mutationFn: api.ackAllAlerts, onSuccess: refresh }),
    setRule: useMutation({
      mutationFn: (v: { kind: string; enabled: boolean }) => api.setAlertRule(v.kind, v.enabled),
      onSuccess: refresh,
    }),
  };
}
