import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import { authStore, useToken } from "@/stores/auth";

export function useMe() {
  const token = useToken();
  return useQuery({
    queryKey: ["me", token],
    queryFn: api.me,
    enabled: token !== null,
    staleTime: Infinity,
    retry: false,
  });
}

export function useLogout(): () => void {
  const qc = useQueryClient();
  return () => {
    authStore.clear();
    qc.clear();
  };
}
