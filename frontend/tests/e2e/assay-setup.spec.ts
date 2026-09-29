import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const width of [1440, 390]) {
  test(`assay setup starts with Base and resumes saved scope selections at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    let saved: Record<string, unknown> | null = null
    const panelForm = { fields: {
      asp_id: { label: "Assay identifier", data_type: "str", display_type: "text" },
      display_name: { label: "Display name", data_type: "str", display_type: "text" },
      asp_group: { data_type: "str", default: "hematology" },
      asp_family: { data_type: "str", default: "panel-dna" },
      asp_category: { data_type: "str", default: "dna" },
    } }
    const context = () => ({ panel_form: panelForm, subpanels: [{ subpanel_id: "myeloid", display_name: "Myeloid", is_active: true }], environments: ["development", "production"], ...(saved ? { setup: saved, history: [], rules: [], readiness: { ready: false, issues: ["Missing ASPCs: base/development"] } } : {}) })
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/admin/assay-setups") {
        if (route.request().method() === "POST") {
          saved = { _id: "setup-1", asp_id: "synthetic-assay", content: route.request().postDataJSON(), status: "draft", revision: 1, created_by: "coyote3.admin", content_editors: ["coyote3.admin"] }
          expect((saved.content as { scopes: string[] }).scopes).toEqual(["base"])
          return { status: 201, json: saved }
        }
        return { json: { items: saved ? [saved] : [] } }
      }
      if (path.endsWith("/assay-setups/context") || path.endsWith("/assay-setups/setup-1/context")) return { json: context() }
      if (path === "/api/v1/admin/assay-setups/setup-1" && route.request().method() === "PUT") {
        saved = { ...saved, content: route.request().postDataJSON().content, revision: Number(saved?.revision) + 1 }
        return { json: saved }
      }
    })
    await page.goto("/admin/assay-setups?setup=new")
    await page.getByLabel("Assay identifier", { exact: true }).fill("synthetic-assay")
    await page.getByLabel("Display name", { exact: true }).fill("Synthetic assay")
    await page.getByRole("button", { name: "Save", exact: true }).click()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeDisabled()
    await expect(page.getByRole("checkbox", { name: "Myeloid", exact: true })).not.toBeChecked()
    await page.getByRole("checkbox", { name: "Myeloid", exact: true }).check()
    await page.getByRole("checkbox", { name: "development", exact: true }).check()
    await page.getByRole("button", { name: "Save scopes" }).click()
    await expect(page.getByText("draft · Revision 2", { exact: true })).toBeVisible()
    await page.reload()
    await page.getByRole("button", { name: "2. Scopes", exact: true }).click()
    await expect(page.getByRole("checkbox", { name: "Base", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "Myeloid", exact: true })).toBeChecked()
    await page.screenshot({ path: testInfo.outputPath(`setup-scopes-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.getByRole("button", { name: "6. Review", exact: true }).click()
    await expect(page.getByRole("button", { name: "Submit for review" })).toBeDisabled()
    await expect(page.getByText("Missing ASPCs: base/development", { exact: true })).toBeVisible()
  })
}
