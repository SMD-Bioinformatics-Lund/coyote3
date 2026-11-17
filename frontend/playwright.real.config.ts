import { defineConfig, devices } from "@playwright/test"
import { deploymentSettings, validateReleaseArguments } from "./tests/e2e-real/support/deployment-settings"

const settings = deploymentSettings(process.env)
// Workers reload this file with their own entry-point arguments; validate in the CLI runner.
if (settings.release && process.argv[2] === "test") validateReleaseArguments(process.argv.slice(2))

export default defineConfig({
  testDir: "./tests/e2e-real",
  timeout: 60_000,
  globalSetup: "./tests/e2e-real/support/setup.ts",
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: settings.release,
  failOnFlakyTests: settings.release,
  reporter: settings.release
    ? [["line"], ["json"], ["./tests/e2e-real/support/require-complete-acceptance.ts"]]
    : "line",
  use: {
    baseURL: settings.baseURL,
    ignoreHTTPSErrors: settings.ignoreHTTPSErrors,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium-real", use: { ...devices["Desktop Chrome"] } }],
})
