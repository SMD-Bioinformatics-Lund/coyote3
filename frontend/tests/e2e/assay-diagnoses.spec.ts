import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const { width, theme } of [
  { width: 1440, theme: "light" },
  { width: 390, theme: "light" },
  { width: 1440, theme: "dark" },
  { width: 390, theme: "dark" },
]) {
  test(`shared definition and assay association pages at ${width}px in ${theme}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const definitions: { diagnosis_id: string; display_name: string; description: string; is_active: boolean; version: number; updated_by: string; associated_asp_ids: string[] }[] = []
    let active = true
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "demo", roles: ["superuser"], role: "superuser", access_level: 99_999,
        permissions: [], ui_settings: { theme },
      } }
      if (path === "/api/v1/resources/asp") return { json: { panels: [{ asp_id: "assay_1", name: "Assay 1", display_name: "Full assay one", is_active: true }], pagination: { total: 1 } } }
      if (path === "/api/v1/resources/diagnoses") {
        if (route.request().method() === "POST") {
          const { asp_ids, ...definition } = route.request().postDataJSON()
          expect(asp_ids).toEqual(["assay_1"])
          definitions.push({ ...definition, associated_asp_ids: asp_ids, version: 1, updated_by: "demo" })
          return { status: 201, json: {} }
        }
        return { json: { diagnoses: [...definitions, { diagnosis_id: "unassociated", display_name: "Unassociated scope", description: "", is_active: true, version: 1, updated_by: "demo" }] } }
      }
      if (path === "/api/v1/resources/asp/assay_1/diagnoses") return { json: { diagnoses: definitions.map((row) => ({ ...row, is_active: active, definition_is_active: true })) } }
      if (path.endsWith("/myeloid-review/status")) {
        active = route.request().postDataJSON().is_active
        return { json: {} }
      }
    })
    await page.goto("/admin")
    await expect(page.locator("html")).toHaveClass(new RegExp(theme))
    await page.getByRole("link", { name: /^Diagnosis definitions/ }).click()
    await page.getByRole("button", { name: "Create diagnosis" }).click()
    await page.getByLabel("Display name", { exact: true }).fill("Myeloid review")
    await page.getByRole("checkbox", { name: /Assay 1/ }).check()
    await page.screenshot({ path: testInfo.outputPath(`definitions-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save diagnosis" }).click()
    await expect(page.getByRole("cell", { name: "Myeloid review myeloid-review", exact: true })).toBeVisible()
    const assayBadge = page.getByRole("link", { name: "Assay 1", exact: true })
    await expect(assayBadge).toHaveAttribute("href", "/admin/assay-diagnoses?assay=assay_1")
    await expect(assayBadge.locator('[data-slot="table-badge"]')).toBeVisible()
    await page.getByRole("tab", { name: "Assay associations", exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/assay-diagnoses$/)
    await page.getByLabel("Assay", { exact: true }).selectOption("assay_1")
    await expect(page.getByRole("button", { name: /Deactivate Myeloid/ })).toBeVisible()
    await expect(page.getByRole("table").getByText("Unassociated scope")).toHaveCount(0)
    await page.getByRole("button", { name: /Deactivate Myeloid/ }).click()
    await expect(page.getByRole("button", { name: /Activate Myeloid/ })).toBeVisible()
    await expect(page.getByText("Inactive", { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`associations-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(definitions).toHaveLength(1)
  })
}
