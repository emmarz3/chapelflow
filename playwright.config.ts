import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.E2E_WEB_PORT || "4173";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "django-integration.spec.ts",
  fullyParallel: true,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: `npm run dev:web -- --host 127.0.0.1 --port ${webPort}`,
    url: `http://127.0.0.1:${webPort}`,
    reuseExistingServer: !process.env.CI,
    env: { VITE_DATA_MODE: "demo", VITE_BACKEND: "typescript", VITE_E2E_TEST: "true" },
    timeout: 120_000,
  },
});
