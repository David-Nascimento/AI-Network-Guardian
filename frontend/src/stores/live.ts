import { useSyncExternalStore } from "react";

export type LiveState = "connecting" | "live" | "offline";

let state: LiveState = "offline";
const listeners = new Set<() => void>();

export const liveStore = {
  get: (): LiveState => state,
  set(next: LiveState): void {
    if (next === state) return;
    state = next;
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useLiveState(): LiveState {
  return useSyncExternalStore(liveStore.subscribe, liveStore.get, () => "offline" as const);
}
