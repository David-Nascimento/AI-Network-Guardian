import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const backend = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5180, // porta própria: evita colidir com outros projetos Vite na 5173
    strictPort: true, // se estiver ocupada, falha em vez de subir em outra porta sem avisar
    proxy: {
      "/api": { target: backend, ws: true },
      "/health": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: false,
    exclude: ["e2e/**", "node_modules/**"],
  },
});
