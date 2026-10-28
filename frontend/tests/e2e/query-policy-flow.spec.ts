import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  for (const width of [1440, 390]) {
    test(`query flow and overrides in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      const oldRule = { id: "old-marker", mode: "exclude", genes: ["TP53"] }
      const activeRule = { id: "active-marker", mode: "admit", condition: { type: "predicate", field: "genes", operator: "in", value: ["CEBPA"] } }
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "demo", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
        if (path.endsWith("/query-rule-sets/options")) return { json: { groups: [{ id: "example", name: "Example group" }], assays: [] } }
        if (path.endsWith("/query-rule-sets")) return { json: { items: [] } }
        if (path.endsWith("/query-rule-sets/preview")) {
          const draft = Boolean(route.request().postDataJSON().content)
          return { json: {
            evidence_mode: draft ? "case_only" : "paired", exceptions: draft ? [activeRule] : [oldRule],
            lineage: [
              { source: "default", version: null, population_frequency_fields: ["gnomad_frequency"], content: { evidence_mode: "paired", exceptions: [], exception_mode: "replace" } },
              { source: "example", version: 1, content: { evidence_mode: null, exceptions: [oldRule], exception_mode: "replace" } },
              ...(draft ? [{ source: "preview", version: null, content: { evidence_mode: "case_only", exceptions: [activeRule], exception_mode: "replace" } }] : []),
            ],
          } }
        }
      })
      await page.goto("/admin/query-rules")
      await page.getByRole("combobox", { name: "Assay group", exact: true }).selectOption("example")
      await page.getByRole("button", { name: "Preview effective policy", exact: true }).click()
      const sidebar = page.getByRole("complementary", { name: "Query policy preview" })
      await sidebar.getByText("Sources and overridden rules", { exact: true }).click()
      await expect(sidebar.getByText("Exceptions replaced by Selected version", { exact: true })).toBeVisible()
      const flow = sidebar.getByRole("region", { name: "Final selection flow" })
      await expect(flow.getByText("active-marker", { exact: true })).toBeVisible()
      await expect(flow.getByText("old-marker", { exact: true })).toHaveCount(0)
      await expect(sidebar.getByText("Application defaults", { exact: true })).toBeVisible()
      await sidebar.getByText("Sources and overridden rules", { exact: true }).click()
      await flow.getByRole("heading", { name: "Final selection flow", exact: true }).scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath("query-flow.png"), fullPage: true })
      await sidebar.getByRole("button", { name: "Currently published", exact: true }).click()
      await expect(flow.getByText("old-marker", { exact: true })).toBeVisible()
      await expect(flow.getByRole("region", { name: "Control evidence" })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    })
  }
}
