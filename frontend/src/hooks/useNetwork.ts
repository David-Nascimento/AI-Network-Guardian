import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import { liveStore } from "@/stores/live";
import type { TargetInput } from "@/types/api";

// Polling é a rede de segurança: com o WebSocket ao vivo ele espaça, sem ele volta a 15 s.
export const REFRESH_MS = 15_000;
export const LIVE_REFRESH_MS = 60_000;
export const pollMs = (): number => (liveStore.get() === "live" ? LIVE_REFRESH_MS : REFRESH_MS);

export function useNetworkStatus() {
  return useQuery({
    queryKey: ["network", "status"],
    queryFn: api.networkStatus,
    refetchInterval: pollMs,
  });
}

export function useTargets() {
  return useQuery({ queryKey: ["network", "targets"], queryFn: api.targets });
}

export function useEvents(hours: number, activeOnly = false) {
  return useQuery({
    queryKey: ["network", "events", hours, activeOnly],
    queryFn: () => api.events({ hours, active_only: activeOnly }),
    refetchInterval: pollMs,
  });
}

export function useHistory(hours: number, bucketMinutes: number, targetId?: number) {
  return useQuery({
    queryKey: ["metrics", "history", hours, bucketMinutes, targetId ?? null],
    queryFn: () => api.history({ hours, bucket_minutes: bucketMinutes, target_id: targetId }),
    refetchInterval: pollMs,
  });
}

export function useSummary(hours: number, targetId?: number) {
  return useQuery({
    queryKey: ["metrics", "summary", hours, targetId ?? null],
    queryFn: () => api.summary({ hours, target_id: targetId }),
    refetchInterval: pollMs,
  });
}

export function useComparison(hours: number, targetId?: number) {
  return useQuery({
    queryKey: ["metrics", "compare", hours, targetId ?? null],
    queryFn: () => api.compare({ hours, target_id: targetId }),
    refetchInterval: pollMs,
  });
}

export function useTargetMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["network"] });
  return {
    create: useMutation({ mutationFn: (b: TargetInput) => api.createTarget(b), onSuccess: refresh }),
    toggle: useMutation({
      mutationFn: (v: { id: number; enabled: boolean }) =>
        api.updateTarget(v.id, { enabled: v.enabled }),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (id: number) => api.deleteTarget(id), onSuccess: refresh }),
  };
}
