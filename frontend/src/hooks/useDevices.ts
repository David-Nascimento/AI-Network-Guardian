import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import type { Device } from "@/types/api";
import { pollMs } from "./useNetwork";

export function useDevices() {
  return useQuery({ queryKey: ["devices"], queryFn: api.devices, refetchInterval: pollMs });
}

export function useDeviceEvents(id: number | null) {
  return useQuery({
    queryKey: ["devices", id, "events"],
    queryFn: () => api.deviceEvents(id as number),
    enabled: id !== null,
  });
}

export function useDevicePorts(id: number) {
  return useQuery({ queryKey: ["devices", id, "ports"], queryFn: () => api.devicePorts(id) });
}

export function useTopology() {
  return useQuery({ queryKey: ["topology"], queryFn: api.topology, refetchInterval: pollMs });
}

export function useDeviceMutations() {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["devices"] });
    void qc.invalidateQueries({ queryKey: ["topology"] });
  };
  return {
    update: useMutation({
      mutationFn: (v: { id: number; changes: Partial<Pick<Device, "custom_name" | "category" | "is_known">> }) =>
        api.updateDevice(v.id, v.changes),
      onSuccess: refresh,
    }),
    scan: useMutation({ mutationFn: api.scanDevices, onSuccess: refresh }),
    scanPorts: useMutation({
      mutationFn: (id: number) => api.scanPorts(id),
      onSuccess: (_, id) => {
        void qc.invalidateQueries({ queryKey: ["devices", id, "ports"] });
        void qc.invalidateQueries({ queryKey: ["devices"] });
      },
    }),
    importNames: useMutation({ mutationFn: (text: string) => api.importNames(text), onSuccess: refresh }),
    markAllKnown: useMutation({ mutationFn: api.markAllKnown, onSuccess: refresh }),
  };
}
