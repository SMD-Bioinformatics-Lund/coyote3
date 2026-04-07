const { defineConfig } = require("@playwright/test");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");

module.exports = defineConfig({
  testDir: ".",
  testMatch: ["critical-flows.spec.js"],
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    trace: "on-first-retry",
  },
  webServer: {
    command:
      "PYTHONPATH=. TESTING=1 MONGO_URI=mongodb://localhost:27017 SCRIPT_NAME=/coyote3 python3 tests/e2e/app_server.py",
    cwd: repoRoot,
    url: "http://127.0.0.1:4173/coyote3/login",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
