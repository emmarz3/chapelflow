import { expect, test } from "@playwright/test";

test("first homepage entry reveals the chapel brand, then stays dismissed on refresh", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const intro = page.locator(".cf-intro");
  await expect(intro).toBeVisible();
  await expect(intro.locator(".cf-intro__wordmark")).toBeVisible({ timeout: 3_000 });
  await expect(intro.locator(".cf-intro__chapel-logo")).toBeVisible({ timeout: 4_000 });
  await expect.poll(() => intro.locator(".cf-intro__chapel-logo").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await expect.poll(() => intro.locator(".cf-intro__wipe").evaluate((element) => element.getBoundingClientRect().left)).toBeGreaterThan(1200);
  await expect(intro).toHaveCount(0, { timeout: 5_000 });
  await expect(page.locator(".cuc-home__hero")).toBeVisible();

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(intro).toHaveCount(0);
  await expect(page.locator(".cuc-home__hero")).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("direct internal and sign-in pages open without the intro", async ({ page }) => {
  await page.goto("/about", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^sign in/i })).toBeVisible();
});

test("reduced motion opens the homepage without waiting", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toHaveCount(0, { timeout: 1_500 });
  await expect(page.locator(".cuc-home__hero")).toBeVisible();
});

test("missing logo bypasses the intro", async ({ page }) => {
  await page.route("**/chrisland-university-chapel-logo.svg", (route) => route.abort());
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".cf-intro")).toHaveCount(0, { timeout: 2_000 });
  await expect(page.locator(".cuc-home__hero")).toBeVisible();
});

test("slow logo loading cannot hold the homepage", async ({ page }) => {
  await page.route("**/chrisland-university-chapel-logo.svg", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 6_000));
    await route.continue();
  });
  await page.goto("/", { waitUntil: "commit" });
  await expect(page.locator(".cf-intro")).toBeVisible();
  await expect(page.locator(".cf-intro")).toHaveCount(0, { timeout: 4_000 });
  await expect(page.locator(".cuc-home__hero")).toBeVisible();
});

test("skip works by keyboard and does not replay after returning home", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const skip = page.getByRole("button", { name: "Skip intro" });
  await skip.focus();
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".cf-intro")).toHaveCount(0);
  await page.getByRole("navigation", { name: /public navigation/i }).getByRole("link", { name: "About" }).click();
  await expect(page).toHaveURL(/\/about$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".cf-intro")).toHaveCount(0);
});

test("slideshow remains controllable on a narrow homepage", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.addInitScript(() => sessionStorage.setItem("chapelflow:intro-seen", "1"));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const carousel = page.getByRole("region", { name: "Chrisland University Chapel photos" });
  await expect(carousel.locator("img.is-active")).toHaveAttribute("src", "/chapel-home-01.jpg");
  await expect.poll(() => carousel.locator("img.is-active").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await expect(carousel.locator("img:not([src])")).toHaveCount(0);
  await carousel.getByRole("button", { name: "Next image" }).click();
  await expect(carousel.locator("img.is-active")).toHaveAttribute("src", "/chapel-home-02.jpg");
  await expect(carousel.locator("img.is-outgoing")).toHaveAttribute("src", "/chapel-home-01.jpg");
  await expect.poll(() => carousel.locator("img.is-active").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await expect(carousel.locator("img.is-outgoing")).toHaveCount(0);
  await carousel.getByRole("button", { name: "Pause slideshow" }).click();
  await expect(carousel.getByRole("button", { name: "Play slideshow" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);
});

for (const width of [375, 768]) {
  test(`intro fits a ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const intro = page.locator(".cf-intro");
    await expect(intro).toBeVisible();
    await expect(intro.getByRole("button", { name: "Skip intro" })).toBeVisible();
    await expect.poll(() => intro.locator(".cf-intro__chapel-logo").evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    await intro.getByRole("button", { name: "Skip intro" }).click();
    await expect(intro).toHaveCount(0);
  });
}
