import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against the real stack (Next.js -> FastAPI -> database -> trained model).
 * Start both servers first (see README "Testing"), or let CI start them.
 * Locally on Windows we reuse the installed Microsoft Edge; CI uses Playwright's Chromium.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, ...(process.env.CI ? {} : { channel: "msedge" }) }, testIgnore: /responsive.spec.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"], ...(process.env.CI ? {} : { channel: "msedge" }) }, testMatch: /responsive\.spec\.ts/ },
  ],
});
