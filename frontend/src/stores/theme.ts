import { useSyncExternalStore } from "react";

export type Theme = "dark" | "light";
const KEY = "ng.theme";
const listeners = new Set<() => void>();

function read(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export const themeStore = {
  get: read,
  set(theme: Theme): void {
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* armazenamento indisponível: vale só para esta sessão */
    }
    applyTheme(theme);
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useTheme(): Theme {
  return useSyncExternalStore(themeStore.subscribe, read, () => "dark" as Theme);
}
