import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("chapelflow:intro-seen", "1");
  });
});

test("public navigation has no route wave and opens pages at the top", async ({
  page,
}) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => window.scrollTo(0, 800));
  await page.getByRole("navigation", { name: /public navigation/i }).getByRole("link", { name: "About" }).click();
  await expect(page).toHaveURL(/\/about$/);
  await expect(page.locator(".route-motion-wave")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  const aboutTop = await page.evaluate(() => window.scrollY);
  expect(aboutTop).toBeLessThan(40);

  await page.evaluate(() => window.scrollTo(0, 600));
  await page.getByRole("navigation", { name: /public navigation/i }).getByRole("link", { name: "Events" }).click();
  await expect(page).toHaveURL(/\/events$/);
  await expect(page.locator(".route-motion-wave")).toHaveCount(0);
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(40);

  await page.getByRole("navigation", { name: /public navigation/i }).getByRole("link", { name: "Sermons" }).click();
  await expect(page).toHaveURL(/\/sermons$/);
  await page.getByRole("navigation", { name: /public navigation/i }).getByRole("link", { name: "Gallery" }).click();
  await expect(page).toHaveURL(/\/gallery$/);
  await expect(page.locator(".route-motion-wave")).toHaveCount(0);
});

test("registration first step stays within a narrow mobile viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/register", { waitUntil: "domcontentloaded" });
  const card = page.locator(".auth-card").first();
  await expect(card).toBeVisible();
  const box = await card.boundingBox();
  expect(box).toBeTruthy();
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(376);
  await expect(page.getByRole("heading", { name: /create your chapelflow account/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /continue/i })).toBeVisible();
});
