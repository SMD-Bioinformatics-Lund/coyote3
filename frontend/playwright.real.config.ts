import { defineConfig, devices } from "@playwright/test"

const baseURL = process.env.COYOTE3_E2E_BASE_URL

if (!baseURL) {
  throw new Error("COYOTE3_E2E_BASE_URL is required for real-deployment browser tests.")
}

const deploymentBaseURL = baseURL.endsWith("/") ? baseURL : `${baseURL}/`

export default defineConfig({
  testDir: "./tests/e2e-real",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: "line",
  use: {
    baseURL: deploymentBaseURL,
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium-real", use: { ...devices["Desktop Chrome"] } }],
})
