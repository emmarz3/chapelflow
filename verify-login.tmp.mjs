import { chromium } from "playwright-core";

const base = "http://localhost:3001";
const browser = await chromium.launch();
const context = await browser.newContext({ reducedMotion: "no-preference" });

// Simulate the exact poisoning scenario: a stale HttpOnly access cookie
// (as left behind after the 15-minute token expiry) plus a csrf cookie.
await context.addCookies([
  { name: "chapelflow_access", value: "stale.invalid.token", domain: "localhost", path: "/" },
  { name: "chapelflow_csrf", value: "stale-csrf-value", domain: "localhost", path: "/" },
]);

const page = await context.newPage();
const errors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("response", (res) => {
  const url = res.url();
  if (url.includes("/api/v1/auth/")) console.log("NET", res.status(), res.request().method(), url.replace(base, ""));
});

// 1. Hit an app route with the stale cookie: the session is genuinely
//    expired, so the app should bounce to /login?reason=expired.
await page.goto(`${base}/app`, { waitUntil: "domcontentloaded" });
await page.waitForURL(/login/, { timeout: 20000 });
console.log("STEP 1 - stale session redirected to:", page.url());

// 2. Sign in with valid credentials despite the stale cookie.
await page.getByLabel("Email, matric number, or staff ID").fill(
  "chapel.admin.main@demo.chapelflow.test",
);
await page.getByLabel(/^Password/).fill("ChangeMe123!");
await page.getByRole("button", { name: /Sign in/ }).click();

// 3. Expect a successful landing on the authenticated home (SPA
//    navigation, so poll the URL rather than waiting for a load event).
await page.waitForFunction(
  () => !window.location.pathname.startsWith("/login"),
  null,
  { timeout: 30000 },
);
console.log("STEP 2 - after sign-in landed on:", page.url());

// 4. The new session must actually work against a protected endpoint.
const me = await page.evaluate(async () => {
  const res = await fetch("/api/v1/auth/me/", {
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  const body = await res.json().catch(() => null);
  return { status: res.status, email: body?.data?.email ?? null };
});
console.log("STEP 3 - /auth/me:", me.status, me.email ?? "");

const stillLogin = page.url().includes("/login");
console.log(stillLogin ? "RESULT: FAIL - still on login" : "RESULT: PASS - logged in");
console.log("console errors:", errors.length ? errors : "none");

await browser.close();
process.exit(stillLogin || me.status !== 200 ? 1 : 0);
