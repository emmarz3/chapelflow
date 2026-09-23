import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.E2E_WEB_PORT || "4174";
const djangoPort = process.env.E2E_DJANGO_PORT || "8001";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "django-integration.spec.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${webPort}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `npm run django:setup && node scripts/dev-django.mjs runserver 127.0.0.1:${djangoPort} --noreload`,
      url: `http://127.0.0.1:${djangoPort}/health/`,
      env: { CHAPELFLOW_LOCAL_DATABASE: "browser-e2e.sqlite3", CSRF_TRUSTED_ORIGINS: `http://127.0.0.1:${webPort}` },
      timeout: 120_000,
    },
    {
      command: `npm run dev:web -- --host 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}`,
      env: { VITE_DATA_MODE: "api", VITE_BACKEND: "django", VITE_E2E_TEST: "true", VITE_API_BASE_URL: "/api/v1", API_PROXY_TARGET: `http://127.0.0.1:${djangoPort}` },
      timeout: 120_000,
    },
  ],
});
