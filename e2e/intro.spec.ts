import { expect, test } from "@playwright/test";

test("brand introduction completes, unmounts, and does not replay in-session", async ({
  page,
}) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toBeVisible();
  await expect(page.locator(".cf-intro")).toHaveCount(0, { timeout: 7_000 });
  await expect(page.getByRole("button", { name: /^sign in/i })).toBeVisible();

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^sign in/i })).toBeVisible();
});

test("reduced motion reaches the application in under one second", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toBeVisible();
  await expect(page.locator(".cf-intro")).toHaveCount(0, { timeout: 1_500 });
  await expect(page.getByRole("button", { name: /^sign in/i })).toBeVisible();
});

test("home page replays the introduction after refresh", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toBeVisible();
  await page.getByRole("button", { name: /skip intro/i }).click();
  await expect(page.locator(".cf-intro")).toHaveCount(0);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toBeVisible();
});
