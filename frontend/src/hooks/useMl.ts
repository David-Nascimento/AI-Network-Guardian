import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

export function useMlStatus() {
  return useQuery({ queryKey: ["ml", "status"], queryFn: api.mlStatus, refetchInterval: 60_000 });
}

export function useAnomalies(hours = 24) {
  return useQuery({
    queryKey: ["ml", "anomalies", hours],
    queryFn: () => api.anomalies(hours),
    refetchInterval: 60_000,
  });
}
