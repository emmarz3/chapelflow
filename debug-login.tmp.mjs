import { chromium } from "playwright-core";

const base = "http://localhost:3001";
const browser = await chromium.launch();
const context = await browser.newContext({ reducedMotion: "no-preference" });
await context.addCookies([
  { name: "chapelflow_access", value: "stale.invalid.token", domain: "localhost", path: "/" },
  { name: "chapelflow_csrf", value: "stale-csrf-value", domain: "localhost", path: "/" },
]);
const page = await context.newPage();
page.on("response", (res) => {
  const url = res.url();
  if (url.includes("/api/")) console.log("NET", res.status(), res.request().method(), url);
});
page.on("requestfailed", (req) => console.log("REQFAIL", req.url(), req.failure()?.errorText));

await page.goto(`${base}/app`, { waitUntil: "domcontentloaded" });
await page.waitForURL(/login/, { timeout: 20000 });
console.log("STEP 1 url:", page.url());

await page.getByLabel("Email, matric number, or staff ID").fill("chapel.admin.main@demo.chapelflow.test");
await page.getByLabel(/^Password/).fill("ChangeMe123!");
await page.getByRole("button", { name: /Sign in/ }).click();

// Give the request + 900ms navigation timer time to settle.
await page.waitForTimeout(6000);
console.log("STEP 2 url after wait:", page.url());
const formError = await page.locator(".form-error").first().textContent().catch(() => null);
const inlineAlert = await page.locator(".inline-alert").first().textContent().catch(() => null);
console.log("form-error:", formError);
console.log("inline-alert:", inlineAlert);
const cookies = await context.cookies();
console.log("cookies:", cookies.map((c) => c.name).join(", "));
await browser.close();
console.log("done");
