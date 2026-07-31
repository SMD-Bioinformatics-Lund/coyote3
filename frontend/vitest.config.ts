import path from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig } from "vitest/config"

const projectRoot = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  define: {
    __COYOTE3_RUNTIME__: JSON.stringify({
      appVersion: "test",
      gensUri: "",
      igvUri: "",
      localTimeZone: "UTC",
      organizationName: "Coyote3 Test",
      scriptName: "",
    }),
  },
  resolve: {
    alias: {
      "@": path.resolve(projectRoot, "src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "lcov"],
      reportsDirectory: "coverage",
      include: [
        "src/lib/**/*.{ts,tsx}",
        "src/components/comments/markdown-format.ts",
        "src/components/notifications/notification-store.ts",
      ],
      exclude: ["src/**/*.d.ts", "src/**/*.test.ts"],
      thresholds: {
        statements: 40,
        branches: 40,
        functions: 40,
        lines: 40,
      },
    },
  },
})
