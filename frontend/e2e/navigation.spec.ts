import { expect, test } from "@playwright/test";

import { loginOk } from "./helpers";

const PAGES: [string, string][] = [
  ["Network Monitor", "Network Monitor"],
  ["Dispositivos", "Dispositivos"],
  ["Topologia", "Topologia"],
  ["Alertas", "Alertas"],
  ["AI Guardian", "AI Guardian"],
  ["Relatórios", "Relatórios"],
  ["Dashboard", "Dashboard"],
];

test("todas as páginas do menu abrem sem erro no console", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await loginOk(page);
  for (const [link, heading] of PAGES) {
    await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: link }).click();
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("sem Ollama configurado o agente aparece desligado, sem inventar respostas", async ({ page }) => {
  await loginOk(page);
  await page.goto("/guardian");
  await expect(page.getByText("Agente desligado")).toBeVisible();
  await expect(page.getByLabel("Pergunta")).toBeDisabled();
});
