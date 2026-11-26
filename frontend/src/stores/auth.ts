import { useSyncExternalStore } from "react";

// sessionStorage: o token some ao fechar a aba (menor janela de exposição que localStorage).
const KEY = "ng.token";
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export const authStore = {
  getToken: read,
  setToken(token: string): void {
    sessionStorage.setItem(KEY, token);
    listeners.forEach((l) => l());
  },
  clear(): void {
    sessionStorage.removeItem(KEY);
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useToken(): string | null {
  return useSyncExternalStore(authStore.subscribe, read, () => null);
}
