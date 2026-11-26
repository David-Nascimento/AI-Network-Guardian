import { defineConfig, devices } from "@playwright/test";

/**
 * E2E contra o sistema real (API + banco SQLite descartável), com agendador desligado para não
 * medir nem varrer a sua rede durante o teste. Pré-requisito: dependências do backend instaladas.
 *
 * Variáveis: E2E_PYTHON (python do venv do backend; padrão "python"), E2E_PASSWORD.
 */
const python = process.env.E2E_PYTHON ?? "python";
export const E2E_USER = "admin";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "senha-e2e-segura-123";

const backendEnv = {
  NG_ENVIRONMENT: "test",
  NG_DATABASE_URL: "sqlite:///./e2e.db",
  NG_ADMIN_USERNAME: E2E_USER,
  NG_ADMIN_PASSWORD: E2E_PASSWORD,
  NG_SCHEDULER_ENABLED: "false",
  NG_SEED_DEFAULT_TARGETS: "false",
  NG_LOGIN_RATE_LIMIT: "1000",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5180", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m alembic upgrade head && ${python} -m uvicorn --factory app.main:create_app --port 8000`,
      cwd: "../backend",
      url: "http://localhost:8000/health",
      env: backendEnv,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5180",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
