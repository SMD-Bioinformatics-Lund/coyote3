import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const writable of [false, true]) {
  test(`application controls transfer with ${writable ? "editing" : "read-only"} access`, async ({ page }) => {
    const controls = { email: { enabled: true }, celery: { enabled: true, maintenance_enabled: true },
      retention: { audit_events_days: 730 }, modules: { reports_enabled: true },
      curation: { tiering: { small_variant_enabled: true } } }
    const writes: unknown[] = []
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "operator", roles: ["operator"],
        permissions: ["app.controls:view", ...(writable ? ["app.controls:edit"] : [])],
        ui_settings: { theme: writable ? "light" : "dark" } } }
      if (path.endsWith("/admin/controls")) {
        if (route.request().method() === "PUT") writes.push(route.request().postDataJSON())
        return { json: { controls: { ...controls, updated_by: "previous-author", updated_on: "2026-01-01" }, runtime: {} } }
      }
    })
    await page.setViewportSize({ width: writable ? 1440 : 390, height: 900 })
    await page.goto("/admin/controls")
    const pending = page.waitForEvent("download")
    await page.getByRole("button", { name: "Export JSON", exact: true }).click()
    const download = await pending
    const contents = await readFile((await download.path())!, "utf8")
    expect(JSON.parse(contents)).toEqual(controls)
    if (!writable) {
      await expect(page.getByRole("button", { name: "Import JSON", exact: true })).toHaveCount(0)
    } else {
      await expect(page.getByRole("button", { name: "Import JSON", exact: true })).toBeEnabled()
      await page.getByLabel("Import application controls JSON").setInputFiles({
        name: "controls.json", mimeType: "application/json", buffer: Buffer.from(contents),
      })
      await expect(page.getByRole("textbox", { name: "Application controls JSON", exact: true })).toBeVisible()
      expect(writes).toEqual([])
      await page.getByRole("button", { name: "Save application controls", exact: true }).click()
      await expect.poll(() => writes).toEqual([{ controls }])
    }
  })
}

for (const theme of ["light", "dark"]) {
  for (const width of [1440, 390]) {
    test(`query configuration export/import in ${theme} at ${width}px`, async ({ page }) => {
      const scope = { assay_group: "example", asp_id: null, diagnosis_id: null,
        analysis: "snv", intent: "somatic", modality: null, family: null, environment: null }
      const portable = { name: "Example selection", scope,
        content: { evidence_mode: "case_only", exceptions: null } }
      const saved = { ...portable, _id: "policy-1", version: 3, revision: 5,
        reason: "Previous decision", status: "published", created_by: "original" }
      const writes: string[] = []
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "demo", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
        if (path.endsWith("/query-rule-sets/options")) return { json: { groups: [{ id: "example", name: "Example group" }], assays: [] } }
        if (path.endsWith("/query-rule-sets")) {
          if (route.request().method() === "POST") writes.push(path)
          return { json: { items: [saved] } }
        }
        if (path.endsWith("/query-rule-sets/preview")) return { json: {
          scope, evidence_mode: "case_only", exceptions: [], lineage: [],
        } }
      })
      await page.setViewportSize({ width, height: 900 })
      await page.goto("/admin/query-rules")
      await page.getByRole("button", { name: /Example selection/ }).click()
      const pending = page.waitForEvent("download")
      await page.getByRole("button", { name: "Export JSON", exact: true }).click()
      const download = await pending
      const contents = await readFile((await download.path())!, "utf8")
      expect(JSON.parse(contents)).toEqual(portable)
      await page.getByLabel("Import query rules JSON").setInputFiles({
        name: "policy.json", mimeType: "application/json", buffer: Buffer.from(contents),
      })
      await expect(page.getByRole("heading", { name: "New draft", exact: true })).toBeVisible()
      await expect(page.getByRole("combobox", { name: "Evidence mode", exact: true })).toHaveValue("case_only")
      await expect(page.getByLabel("Change or review reason")).toHaveValue("")
      await expect(page.getByRole("button", { name: "Save draft", exact: true })).toBeDisabled()
      expect(writes).toEqual([])
      await page.getByRole("button", { name: "Import JSON", exact: true }).focus()
      await expect(page.getByRole("button", { name: "Import JSON", exact: true })).toBeFocused()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await page.screenshot({ path: `test-results/configuration-transfer-${theme}-${width}.png`, fullPage: true })
    })
  }
}
