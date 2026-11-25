import { expect, test } from "@playwright/test";

test("mobile layout: landing and app shell have no horizontal overflow and a working menu", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Know Pune's air/ })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);

  const email = `m-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Mobile Tester");
  await page.getByLabel("Email").fill(email);
  await page.locator("#password").fill("Mobile1234");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Pune air quality" })).toBeVisible();
  const appOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(appOverflow).toBeLessThanOrEqual(1);

  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Model Lab" }).click();
  await expect(page.getByRole("heading", { name: "Model Lab" })).toBeVisible();
});
