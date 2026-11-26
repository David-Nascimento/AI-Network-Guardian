import { expect, test } from "@playwright/test";

import { loginOk } from "./helpers";

test("administrador cadastra um destino e ele aparece na lista", async ({ page }) => {
  await loginOk(page);
  await page.goto("/network");
  const name = `Alvo E2E ${Date.now()}`;
  await page.getByLabel("Nome", { exact: true }).fill(name);
  await page.getByLabel("Host ou IP").fill("192.0.2.10"); // faixa de documentação (RFC 5737)
  await page.getByRole("button", { name: "Adicionar" }).click();
  await expect(page.getByText(name)).toBeVisible();
  await page.getByRole("button", { name: `Remover ${name}` }).click();
  await expect(page.getByText(name)).toHaveCount(0);
});

test("relatório mostra o aviso de que nada é estimado e exporta CSV", async ({ page }) => {
  await loginOk(page);
  await page.goto("/reports");
  await expect(page.getByText(/nada é estimado/).first()).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Dispositivos (CSV)" }).click();
  expect((await download).suggestedFilename()).toMatch(/^guardian-devices-.*\.csv$/);
});

test("central de alertas lista as regras fixas e mantém 'conhecido offline' desligado", async ({ page }) => {
  await loginOk(page);
  await page.goto("/alerts");
  await expect(page.getByLabel(/Novo dispositivo/)).toBeChecked();
  await expect(page.getByLabel(/Aparelho conhecido ficou offline/)).not.toBeChecked();
});
