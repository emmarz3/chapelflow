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

test("service, contact, and protected routes open directly without transition overlays", async ({ page }) => {
  for (const route of ["/service-times", "/contact", "/login"]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".cf-intro, .route-motion-wave")).toHaveCount(0);
    await expect(page.locator("main").first()).toBeVisible();
  }
  await page.goto("/app", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro, .route-motion-wave")).toHaveCount(0);
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
});

test("signed-in member opens the dashboard without a public intro", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("chapelflow-demo-role", "member"));
  await page.goto("/app", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/app(?:\/|$)/);
  await expect(page.locator(".cf-intro, .route-motion-wave")).toHaveCount(0);
});

test("chapel story and university statements fit the mobile homepage", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Our Role" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Belonging, Purpose & Growth" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Our Vision" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Our Mission" })).toBeVisible();
  await expect(page.getByText("Rev. Canon Oluwajuwonlo Onasanya")).toBeVisible();
  await expect(page.getByRole("link", { name: /see programs & upcoming events/i })).toHaveAttribute("href", "/events");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);
});

test("saved dark theme keeps homepage and auth text readable", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("chapelflow-theme", "dark"));
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".auth-heading h1")).toHaveCSS("color", "rgb(245, 241, 247)");
  await expect(page.locator(".auth-card label").first()).toHaveCSS("color", "rgb(245, 241, 247)");
  await expect(page.locator(".auth-card input").first()).toHaveCSS("background-color", "rgb(48, 41, 56)");

  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/register", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".auth-heading h1")).toBeVisible();
  await expect(page.locator(".auth-card label").first()).toBeVisible();
  await expect(page.locator(".auth-heading h1")).toHaveCSS("color", "rgb(245, 241, 247)");
  await expect(page.locator(".auth-card label").first()).toHaveCSS("color", "rgb(245, 241, 247)");
  await expect.poll(() => page.locator(".auth-card form").evaluate((element) => Number(getComputedStyle(element).opacity))).toBeGreaterThan(0.99);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cuc-home__pillars h3").first()).toHaveCSS("color", "rgb(245, 241, 247)");
  await expect(page.locator(".cuc-home__university h2")).toHaveCSS("color", "rgb(245, 241, 247)");
});
