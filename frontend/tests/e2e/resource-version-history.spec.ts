import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  for (const [resource, key, listKey] of [["asp", "asp_id", "panels"], ["aspc", "aspc_id", "assay_configs"], ["genelists", "isgl_id", "genelists"]] as const) {
    test(`${resource} history loads on demand in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 })
      const row = { [key]: "synthetic", name: "Synthetic", display_name: "Synthetic resource", version: 2, is_active: true }
      const historyReads: string[] = []
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
        if (path === `/api/v1/resources/${resource}`) return { json: { [listKey]: [row] } }
        if (path.startsWith(`/api/v1/resources/${resource}/`) && path.endsWith("/versions")) {
          expect(route.request().method()).toBe("GET")
          historyReads.push(path)
          return { json: [{ ...row, _id: "current" }, { ...row, _id: "old", version: 1, is_active: false, description: "Retained original content" }] }
        }
      })
      await page.goto(`/admin/${resource}`)
      const action = page.getByRole("button", { name: "Version history for synthetic", exact: true })
      await expect(action).toBeVisible()
      expect(historyReads).toEqual([])
      await expect(page.getByRole("region", { name: /version history$/ })).toHaveCount(0)
      await action.click()
      const history = page.getByRole("region", { name: /version history$/ })
      await expect(history.getByText("Version 1 · Retired", { exact: true })).toBeVisible()
      expect(historyReads).toEqual([`/api/v1/resources/${resource}/synthetic/versions`])
      await history.getByText("Version 1 · Retired", { exact: true }).click()
      await expect(history.getByText(/Retained original content/)).toBeVisible()
      await expect(history.getByRole("button", { name: /save|publish|edit/i })).toHaveCount(0)
      await page.screenshot({ path: testInfo.outputPath(`${resource}-history-${theme}.png`), fullPage: true })
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await history.getByRole("button", { name: "Close history" }).click()
      await expect(history).toHaveCount(0)
    })
  }

  test(`governed lists distinguish current and retired publications in ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const reads: string[] = []
    const scope = { assay_group: "synthetic", asp_id: null, diagnosis_id: null, analysis: "snv", intent: "somatic" }
    await installApiFixtures(page, (path, url) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic-author", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path.endsWith("/query-rule-sets/options")) return { json: { groups: [{ id: "synthetic", name: "Synthetic" }], assays: [] } }
      if (path.endsWith("/query-rule-sets/preview")) return { json: { scope, evidence_mode: "paired", exceptions: [], lineage: [] } }
      if (path.endsWith("/query-rule-sets")) {
        reads.push(url.search)
        const retired = url.searchParams.get("status") === "retired"
        return { json: { items: [{ _id: "query", name: retired ? "Past query" : "Current query", scope, content: {}, version: 1, revision: 1, status: retired ? "retired" : "published", created_by: "synthetic-author" }] } }
      }
      if (path.endsWith("/configuration-profiles")) {
        reads.push(url.search)
        const retired = url.searchParams.get("is_current") === "false"
        return { json: [{ _id: "profile", profile_id: "synthetic", name: retired ? "Past profile" : "Current profile", status: "published", is_current: !retired, version: 1, content_hash: "a".repeat(64), created_by: "synthetic-author", content: {}, bindings: [] }] }
      }
      if (path.endsWith("/clinical-rule-sets/facts")) return { json: { items: [] } }
      if (path.endsWith("/clinical-rule-sets/authoring-options")) return { json: { assays: [], condition_values: {}, clinical_reviewers: [], publishers: [] } }
      if (path.endsWith("/clinical-rule-sets")) {
        reads.push(url.search)
        const retired = url.searchParams.get("status") === "retired"
        return { json: { items: [{ _id: "report", rule_set_id: "synthetic__base__sv", name: retired ? "Past report rules" : "Current report rules", scope: { asp_id: "synthetic", diagnosis_id: "base", analyte: "dna", language: "sv" }, content_version: 1, revision: 1, status: "published", active: !retired, blocks: [] }] } }
      }
    })
    for (const [path, currentName, pastName, retiredQuery] of [
      ["/admin/query-rules", "Current query", "Past query", "?status=retired"],
      ["/admin/configuration-profiles", "Current profile", "Past profile", "?status=published&is_current=false"],
      ["/admin/clinical-rules", "Current report rules", "Past report rules", "?q=&status=retired"],
    ]) {
      reads.length = 0
      await page.goto(path)
      await expect(page.getByText(currentName, { exact: true })).toBeVisible()
      expect(reads).not.toContain(retiredQuery)
      await expect(page.getByText(pastName, { exact: true })).toHaveCount(0)
      await page.getByRole("button", { name: "Browse retired versions", exact: true }).click()
      await expect(page.getByText(pastName, { exact: true })).toBeVisible()
      expect(reads).toContain(retiredQuery)
      await page.getByRole("button", { name: "Hide retired versions", exact: true }).click()
      await expect(page.getByText(currentName, { exact: true })).toBeVisible()
    }
  })
}
