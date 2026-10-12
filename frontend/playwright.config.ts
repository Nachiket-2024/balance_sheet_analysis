import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 5173);
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;
const WORKERS = process.env.PLAYWRIGHT_WORKERS
  ? Number(process.env.PLAYWRIGHT_WORKERS)
  : process.env.CI
    ? 2
    : undefined;
const SERVER_COMMAND = process.env.PLAYWRIGHT_USE_PREVIEW === "1"
  ? `npm run build && npm run preview -- --host 127.0.0.1 --port ${PORT}`
  : `npm run dev -- --host 127.0.0.1 --port ${PORT}`;

// These suites deliberately exercise different layers of the browser stack.
// The real-account matrix logs into dozens of accounts against one disposable
// backend and is exhaustive in Chromium desktop. Repeating the same matrix in
// Firefox, WebKit, and mobile multiplies backend contention without adding
// authorization coverage: the mocked matrix already runs in every browser.
const REAL_ACCOUNT_MATRIX = "**/authorization/permission_matrix_real_accounts_browser.spec.ts";
const RESPONSIVENESS_TIMING = "**/performance/management_responsiveness_browser.spec.ts";

export default defineConfig({
  testDir: "../tests/frontend",
  testMatch: "**/e2e/**/*.spec.ts",
  timeout: 30_000,
  // The real-account matrix drives the shared dev backend and database. A
  // bounded CI worker count prevents browser scheduling and API contention
  // from turning healthy tests into timeout flakes on standard runners.
  workers: WORKERS,
  // Browser startup and scheduling on shared CI runners can occasionally
  // exceed an individual assertion's timing budget without indicating a
  // product failure. Keep local runs strict, but retry a failed test in CI
  // so one transient browser stall does not fail the whole matrix.
  retries: process.env.CI ? 2 : 0,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: BASE_URL,
    navigationTimeout: 20_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: SERVER_COMMAND,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 7"] },
      testIgnore: [REAL_ACCOUNT_MATRIX],
    },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] },
      testIgnore: [REAL_ACCOUNT_MATRIX, RESPONSIVENESS_TIMING],
    },
    {
      name: "webkit-desktop",
      use: { ...devices["Desktop Safari"] },
      testIgnore: [REAL_ACCOUNT_MATRIX, RESPONSIVENESS_TIMING],
    },
  ],
});
