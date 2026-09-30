import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const width of [1440, 390]) {
  test(`shared definition and assay association pages at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const definitions: { subpanel_id: string; display_name: string; description: string; is_active: boolean; version: number }[] = []
    let active = true
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/resources/asp") return { json: { panels: [{ asp_id: "assay_1", display_name: "Assay 1", is_active: true }], pagination: { total: 1 } } }
      if (path === "/api/v1/resources/subpanels") {
        if (route.request().method() === "POST") {
          const { asp_ids, ...definition } = route.request().postDataJSON()
          expect(asp_ids).toEqual(["assay_1"])
          definitions.push({ ...definition, version: 1 })
          return { status: 201, json: {} }
        }
        return { json: { subpanels: [...definitions, { subpanel_id: "unassociated", display_name: "Unassociated scope", description: "", is_active: true, version: 1 }] } }
      }
      if (path === "/api/v1/resources/asp/assay_1/subpanels") return { json: { subpanels: definitions.map((row) => ({ ...row, is_active: active, definition_is_active: true })) } }
      if (path.endsWith("/myeloid_review/status")) {
        active = route.request().postDataJSON().is_active
        return { json: {} }
      }
    })
    await page.goto("/admin")
    await page.getByRole("link", { name: /^Subpanel definitions/ }).click()
    await page.getByRole("button", { name: "Create subpanel" }).click()
    await page.getByLabel("Display name", { exact: true }).fill("Myeloid review")
    await page.getByRole("checkbox", { name: /Assay 1/ }).check()
    await page.screenshot({ path: testInfo.outputPath(`definitions-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save subpanel" }).click()
    await expect(page.getByRole("cell", { name: "Myeloid review myeloid_review", exact: true })).toBeVisible()
    await page.getByRole("tab", { name: "Assay associations", exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/assay-subpanels$/)
    await page.getByLabel("Assay", { exact: true }).selectOption("assay_1")
    await expect(page.getByRole("button", { name: /Deactivate Myeloid/ })).toBeVisible()
    await expect(page.getByText("Unassociated scope")).toHaveCount(0)
    await page.getByRole("button", { name: /Deactivate Myeloid/ }).click()
    await expect(page.getByRole("button", { name: /Activate Myeloid/ })).toBeVisible()
    await expect(page.getByText("Inactive", { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`associations-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(definitions).toHaveLength(1)
  })
}
