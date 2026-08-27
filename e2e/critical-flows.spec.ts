import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => sessionStorage.clear());
});

test("public chapel site exposes primary journeys", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveTitle(/ChapelFlow/);
  await expect(
    page.getByRole("heading", { name: /chapel community for every part/i }),
  ).toBeVisible();
  await page.getByRole("link", { name: /watch latest sermon/i }).click();
  await expect(page).toHaveURL(/\/sermons$/);
  await expect(
    page.getByRole("heading", { name: /truth for the life/i }),
  ).toBeVisible();
});

test("administrator can sign in and open attendance", async ({ page }) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/email, matric number/i).fill("admin@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("chapel_admin");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(
    page.getByRole("heading", { name: /good morning/i }),
  ).toBeVisible();
  await page.goto("/app/attendance", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: /sunday worship service/i }),
  ).toBeVisible();
});

test("member navigation excludes administrative records", async ({ page }) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/email, matric number/i).fill("member@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("member");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(
    page.getByRole("heading", { name: /welcome back, favour/i }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Members" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Finance" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Sermons & media" })).toHaveCount(
    0,
  );
});

test("protected routes redirect anonymous and unauthorized users", async ({
  page,
}) => {
  await page.goto("/app/members", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel(/email, matric number/i).fill("member@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("member");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/members", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/access-denied$/);
  await expect(
    page.getByRole("heading", { name: /^access restricted$/i }),
  ).toBeVisible();
  await page.goto("/app/media", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/access-denied$/);
});

test("read-only ministry roles do not receive mutation controls", async ({
  page,
}) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/email, matric number/i).fill("pastor@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("pastor");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(page).toHaveURL(/\/app$/);

  await page.goto("/app/members", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: /add member/i })).toHaveCount(
    0,
  );
  await page.goto("/app/workers", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("button", { name: /create roster/i }),
  ).toHaveCount(0);
});

test("theme and keyboard search preferences survive navigation", async ({
  page,
}, testInfo) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/email, matric number/i).fill("admin@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("chapel_admin");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(page).toHaveURL(/\/app$/);

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: /^more$/i }).click();
  }
  await page.getByRole("button", { name: /switch to dark theme/i }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByPlaceholder(/search members, events, records, and pages/i),
  ).toBeFocused();
});

test("offline and reduced-motion preferences receive visible feedback", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(Navigator.prototype, "onLine", {
      configurable: true,
      get: () => false,
    });
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const transitionSeconds = await page
    .getByRole("button", { name: /^sign in/i })
    .evaluate((node) =>
      Number.parseFloat(getComputedStyle(node).transitionDuration),
    );
  expect(transitionSeconds).toBeLessThanOrEqual(0.001);

  await page.getByLabel(/email, matric number/i).fill("admin@example.edu.ng");
  await page.getByLabel(/^password/i).fill("secure-password");
  await page.getByLabel(/preview role/i).selectOption("chapel_admin");
  await page.getByRole("button", { name: /^sign in/i }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText(/you are offline/i)).toBeVisible();
});

test("registration preserves progress and records policy acceptance", async ({
  page,
}) => {
  await page.goto("/register", { waitUntil: "domcontentloaded" });
  await page.getByLabel(/university email/i).fill("student@example.edu.ng");
  await page.getByLabel(/create password/i).fill("secure-password-1");
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/first name/i).fill("Ada");
  await page.getByLabel(/last name/i).fill("Okafor");
  await page.getByLabel(/matric number/i).fill("CU/26/101");
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/read and accept/i).check();
  await page.getByRole("button", { name: /submit registration/i }).click();
  await expect(
    page.getByRole("heading", { name: /check your email/i }),
  ).toBeVisible();
});

test("mobile layout exposes a usable navigation control", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "mobile");
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /open navigation/i }).click();
  await expect(page.locator('.mobile-menu a[href="/events"]')).toBeVisible();
  await expect(
    page.getByRole("link", { name: /join the chapel/i }),
  ).toBeVisible();
});
