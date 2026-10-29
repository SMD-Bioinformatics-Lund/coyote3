import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  for (const width of [390, 1440]) {
    test(`diagnosis actions ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 960 })
      await installApiFixtures(page, (path) => {
        if (path === "/api/v1/auth/whoami") return { json: {
          username: "synthetic_admin", roles: [],
          permissions: ["assay.panel:list", "assay.panel:view", "assay.panel:edit"],
          ui_settings: { theme },
        } }
        if (path === "/api/v1/resources/diagnoses") return { json: { diagnoses: [
          { diagnosis_id: "installed", display_name: "Installed diagnosis", description: "Synthetic protected definition.", is_active: true, version: 1, system_installed: true, updated_by: "system", associated_asp_ids: [] },
          { diagnosis_id: "editable", display_name: "Editable diagnosis", description: "Synthetic editable definition.", is_active: true, version: 2, updated_by: "synthetic_admin", associated_asp_ids: [] },
        ] } }
        if (path === "/api/v1/resources/asp") return { json: { panels: [], pagination: { total: 0 } } }
        return undefined
      })
      await page.goto("/admin/diagnoses")
      const view = page.getByRole("button", { name: "View Installed diagnosis", exact: true })
      await view.focus()
      await page.keyboard.press("Enter")
      const details = page.getByRole("region", { name: "Diagnosis details" })
      await expect(details).toBeFocused()
      await expect(details).toContainText("System-installed definition")
      await expect(page.getByRole("button", { name: "Edit Installed diagnosis", exact: true })).toHaveCount(0)
      await page.screenshot({ path: testInfo.outputPath(`diagnosis-view-${theme}-${width}.png`), fullPage: true })
      await page.getByRole("button", { name: "Close diagnosis details" }).click()
      await page.getByRole("button", { name: "Deactivate Editable diagnosis", exact: true }).click()
      const confirmation = page.getByRole("alertdialog")
      await expect(confirmation).toContainText("across all associated assays")
      await expect(confirmation.getByRole("button", { name: "Cancel", exact: true })).toBeFocused()
      await page.keyboard.press("Escape")
      await expect(confirmation).toHaveCount(0)
    })
  }
}
