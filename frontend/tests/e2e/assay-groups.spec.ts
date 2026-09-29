import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const width of [1440, 390]) {
  test(`assay group creation and system ownership at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const groups = [{ group_id: "solid", display_name: "Solid tumors", description: "Solid tumor assays", system_managed: true, is_active: true, version: 1 }]
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/assay-groups/solid/impact")) return { json: { group: groups[0], assays: ["panel-a"] } }
      if (path.endsWith("/assay-groups/solid/status")) {
        expect(route.request().postDataJSON().reason).toBe("Pause new work")
        groups[0].is_active = route.request().postDataJSON().is_active
        groups[0].version++
        return { json: {} }
      }
      if (path !== "/api/v1/resources/assay-groups") return
      if (route.request().method() === "POST") {
        groups.push({ ...route.request().postDataJSON(), created_by: "test.author", system_managed: false, is_active: true, version: 1 })
        return { status: 201, json: {} }
      }
      return { json: { groups } }
    })
    await page.goto("/admin")
    await expect(page.getByRole("heading", { name: "Assays and subpanels" })).toBeVisible()
    await page.getByRole("textbox", { name: "Search administration" }).fill("clinical rule testing")
    await expect(page.getByRole("link", { name: /^Clinical Rule Testing/ })).toBeVisible()
    await expect(page.getByRole("link", { name: /^Assay groups/ })).toHaveCount(0)
    await page.getByRole("button", { name: "Clear search" }).click()
    await page.screenshot({ path: testInfo.outputPath(`admin-home-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole("link", { name: /^Assay groups/ }).click()
    await expect(page.getByRole("cell", { name: "System", exact: true })).toBeVisible()
    await page.getByRole("button", { name: "Create group" }).click()
    await page.getByLabel("Display name", { exact: true }).fill("Methylation")
    await expect(page.getByLabel("Group identifier", { exact: false })).toHaveValue("methylation")
    await page.screenshot({ path: testInfo.outputPath(`group-form-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Save group" }).click()
    await expect(page.getByRole("cell", { name: "test.author", exact: true })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "Actions", exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`groups-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    expect(groups).toHaveLength(2)
    await page.getByRole("button", { name: "Deactivate Solid tumors" }).click()
    await expect(page.getByText("panel-a", { exact: true })).toBeVisible()
    await page.getByLabel("Reason", { exact: true }).pressSequentially("Pause new work")
    await expect(page.getByLabel("Reason", { exact: true })).toHaveValue("Pause new work")
    await page.getByLabel("Reason", { exact: true }).press("Shift+Tab")
    await expect(page.getByRole("button", { name: "Deactivate group", exact: true })).toBeFocused()
    await page.keyboard.press("Tab")
    await expect(page.getByLabel("Reason", { exact: true })).toBeFocused()
    await page.screenshot({ path: testInfo.outputPath(`group-status-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "Deactivate group", exact: true }).click()
    await expect(page.getByRole("button", { name: "Activate Solid tumors" })).toBeVisible()
  })
}
