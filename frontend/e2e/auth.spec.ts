import { expect, test } from "@playwright/test";

import { login, loginOk } from "./helpers";

test("rota protegida sem sessão leva ao login", async ({ page }) => {
  await page.goto("/devices");
  await expect(page).toHaveURL(/\/login/);
});

test("senha errada mostra erro e não entra", async ({ page }) => {
  await login(page, "senha-errada-qualquer");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("login correto abre o dashboard e sair volta ao login", async ({ page }) => {
  await loginOk(page);
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("o token fica só na sessão da aba, nunca na URL", async ({ page }) => {
  await loginOk(page);
  expect(page.url()).not.toMatch(/token|eyJ/);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});
