import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("diagnosis bulk example and reviewed upload use the existing create endpoint", async ({ page }) => {
  const created: unknown[] = []
  await installApiFixtures(page, (path, _url, route) => {
    if (path === "/api/v1/resources/diagnoses") {
      if (route.request().method() === "POST") {
        created.push(route.request().postDataJSON())
        return { status: 201, json: { status: "ok" } }
      }
      return { json: { diagnoses: [] } }
    }
  })
  await page.goto("/admin/diagnoses")
  await page.getByRole("button", { name: "Show example" }).click()
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('"diagnosis_id"')
  await page.keyboard.press("Escape")
  await expect(dialog).not.toBeVisible()
  await page.getByLabel("Bulk upload diagnoses").setInputFiles({
    name: "diagnoses.yaml", mimeType: "application/yaml",
    buffer: Buffer.from("- diagnosis_id: synthetic-scope\n  display_name: Synthetic scope\n  asp_ids: []\n"),
  })
  await expect(dialog).toContainText("1 records")
  expect(created).toEqual([])
  await page.getByRole("button", { name: "Install records" }).click()
  await expect(dialog).toContainText("synthetic-scope: Created")
  expect(created).toEqual([{ diagnosis_id: "synthetic-scope", display_name: "Synthetic scope", asp_ids: [] }])
  await expect(page.getByRole("button", { name: "Install records" })).toBeDisabled()
  await page.getByRole("button", { name: "Close", exact: true }).click()
  await page.getByRole("button", { name: "Paste JSON / YAML" }).click()
  const editor = page.getByLabel("Bulk records", { exact: true })
  await editor.fill('[{"diagnosis_id":')
  await expect(editor).toHaveAttribute("aria-invalid", "true")
  await expect(page.getByRole("button", { name: "Review records" })).toBeDisabled()
  await page.getByLabel("Content format").selectOption("yaml")
  await editor.fill("- diagnosis_id: synthetic-pasted\n  display_name: Synthetic pasted\n  asp_ids: []")
  await expect(editor).toHaveAttribute("aria-invalid", "false")
  expect(created).toHaveLength(1)
  await page.getByRole("button", { name: "Review records" }).click()
  await page.getByRole("button", { name: "Install records" }).click()
  await expect(dialog).toContainText("synthetic-pasted: Created")
  expect(created).toHaveLength(2)
})
