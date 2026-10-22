import { expect, test } from "@playwright/test";

test.describe("Auth pages — video background", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem("chapelflow:intro-seen", "1");
    });
  });

  test("login page loads with video background", async ({ page }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    const video = page.locator(".auth-visual__video.is-current");
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("autoplay", "");
    await expect(video).toHaveJSProperty("muted", true);
    await expect(video).toHaveAttribute("playsinline", "");
    await expect(video).toHaveAttribute("preload", "metadata");
    await expect(video).toHaveAttribute("disableremoteplayback", "");
    await expect(video).toHaveAttribute("tabindex", "-1");
    await expect(video).not.toHaveAttribute("poster");

    // Brand overlay should be visible
    const branding = page.locator(".auth-visual__branding");
    await expect(branding).toBeVisible();
    await expect(page.locator(".auth-visual__mark")).toBeVisible();
    await expect(page.locator(".auth-visual__tagline")).toHaveText(
      "Nurturing faith. Shaping lives. Impacting Nigeria.",
    );
  });

  test("register page loads with video background and wider card", async ({ page }) => {
    await page.goto("/register", { waitUntil: "domcontentloaded" });

    const video = page.locator(".auth-visual__video.is-current");
    await expect(video).toBeVisible();
    await expect(video).toHaveAttribute("poster", "/chapelflow-auth-register-visual.png");

    // Register card should be wider
    const card = page.locator(".auth-card");
    await expect(card).toBeVisible();

    // Stepper should be present
    await expect(page.locator(".stepper")).toBeVisible();
  });

  test("video cycles on login page after 8 seconds", async ({ page }) => {
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    const video = page.locator(".auth-visual__video.is-current");
    const firstSrc = await video.getAttribute("src");
    expect(firstSrc).toBeTruthy();

    // Wait for cycle (8s interval + 800ms cross-fade = ~8.8s, wait 9.5s to be safe)
    await page.waitForTimeout(9500);

    const secondSrc = await video.getAttribute("src");
    expect(secondSrc).not.toBe(firstSrc);
  });

  test("register page uses different video set", async ({ page }) => {
    await page.goto("/register", { waitUntil: "domcontentloaded" });
    const registerVideo = page.locator(".auth-visual__video.is-current");
    const registerSrc = await registerVideo.getAttribute("src");

    await page.goto("/login", { waitUntil: "domcontentloaded" });
    const loginVideo = page.locator(".auth-visual__video.is-current");
    const loginSrc = await loginVideo.getAttribute("src");

    expect(registerSrc).not.toBe(loginSrc);
  });

  test("reduced motion preference shows a static non-image login background", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    // Video should not be present when reduced motion is preferred
    await expect(page.locator(".auth-visual__video")).toHaveCount(0);

    // No generated image is used as the reduced-motion fallback.
    const fallback = page.locator(".auth-visual__poster--static");
    await expect(fallback).toBeVisible();
    await expect(fallback).not.toHaveAttribute("src");
  });

  test("mobile layout shows full-screen video with glass card", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    // Visual should be fixed full-screen
    const visual = page.locator(".auth-visual");
    await expect(visual).toHaveCSS("position", "fixed");
    await expect(visual).toHaveCSS("z-index", "0");

    // Video should have blur and scale
    const video = page.locator(".auth-visual__video");
    await expect(video).toHaveCSS("filter", "blur(6px)");
    await expect(video).toHaveCSS("transform", "matrix(1.1, 0, 0, 1.1, 0, 0)");

    // Card should be glass-morphism
    const card = page.locator(".auth-card");
    await expect(card).toHaveCSS("background-color", "rgba(255, 255, 255, 0.97)");
    await expect(card).toHaveCSS("border-radius", "16px");

    // Brand overlay should be responsive
    await expect(page.locator(".auth-visual__mark")).toHaveCSS("width", "40px");
  });

  test("top bar is fixed on mobile with gradient background", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/login", { waitUntil: "domcontentloaded" });

    const topBar = page.locator(".auth-main__bar");
    await expect(topBar).toHaveCSS("position", "fixed");
    await expect(topBar).toHaveCSS("top", "0px");
    await expect(topBar).toHaveCSS("z-index", "2");
  });
});
