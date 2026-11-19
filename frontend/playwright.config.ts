import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  failOnFlakyTests: Boolean(process.env.CI),
  workers: 2,
  reporter: process.env.CI
    ? [["line"], ["./tests/e2e-real/support/require-complete-acceptance.ts"]]
    : "line",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    // Unmatched fixture requests must not reach an ambient application backend.
    env: { COYOTE4_API_INTERNAL_URL: "http://127.0.0.1:1" },
    reuseExistingServer: false,
  },
})
