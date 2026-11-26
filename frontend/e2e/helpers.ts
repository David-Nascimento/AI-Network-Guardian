import { expect, type Page } from "@playwright/test";

import { E2E_PASSWORD, E2E_USER } from "../playwright.config";

export async function login(page: Page, password = E2E_PASSWORD): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Usuário").fill(E2E_USER);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
}

export async function loginOk(page: Page): Promise<void> {
  await login(page);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}
