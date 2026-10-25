import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("permissions combine identity and provenance while wrapping descriptions", async ({ page }) => {
  const description = "Review CNV findings and apply supported curation actions while preserving clinical interpretation and the complete review history. ".repeat(4)
  await installApiFixtures(page, (path) => path === "/api/v1/permissions" ? { json: { permission_policies: [{
    permission_id: "cnv:manage", label: "Manage CNVs", category: "Analysis Actions",
    description, tags: [], is_active: true, version: 1,
    created_by: "system", updated_by: "system", system_installed: true,
    created_on: new Date(Date.now() - 604800000).toISOString(),
    updated_on: new Date(Date.now() - 60000).toISOString(),
  }] } } : undefined)
  await page.goto("/admin/permissions")
  const table = page.getByRole("table").first()
  await expect(table.getByRole("columnheader", { name: "Permission", exact: true })).toBeVisible()
  await expect(table.getByRole("columnheader", { name: /Updated On|Label|Permission Id/ })).toHaveCount(0)
  const identity = table.locator('td[data-column-id="permission_id"]')
  await expect(identity).toContainText("Manage CNVs")
  await expect(identity).toContainText("cnv:manage")
  await expect(table.locator('td[data-column-id="record_provenance"]')).toContainText("7 d ago")
  await expect(table.locator('td[data-column-id="updated_by"]')).toContainText("1 min ago")
  const text = table.locator('td[data-column-id="description"] span')
  await expect(text).toHaveCSS("white-space", "pre-wrap")
  await expect(text).toHaveCSS("text-overflow", "clip")
  expect(await text.evaluate((node) => node.scrollHeight <= node.clientHeight)).toBe(true)
})
