import { expect, test, type Page } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("a second editor is read-only until the first editor leaves", async ({ page, browser }) => {
  let owner: string | null = null
  let savedName = "Shared draft"
  let revision = 1
  const install = async (target: Page) => installApiFixtures(target, (path, _url, route) => {
    if (path.startsWith("/api/v1/editing/")) {
      const editor = route.request().postDataJSON().editor_id as string
      if (path.endsWith("/release") && owner === editor) owner = null
      if (path.endsWith("/acquire") && !owner) owner = editor
      return { json: { owned: owner === editor, owner: "editor.one", expires_at: new Date(Date.now() + 90_000).toISOString(), renew_after_seconds: 30 } }
    }
    const setup = { _id: "setup-one", asp_id: "synthetic", revision, status: "draft", content_editors: ["editor.one"], content: { panel: { asp_id: "synthetic", display_name: savedName }, scopes: ["base"], environments: [], gene_lists: [], configurations: [] } }
    if (path === "/api/v1/admin/assay-setups") return { json: { items: [setup] } }
    if (path.endsWith("/assay-setups/setup-one/context") || path.endsWith("/assay-setups/context")) return { json: {
      ...(path.endsWith("/setup-one/context") ? { setup } : {}), panel_form: { fields: { asp_id: { label: "Assay identifier", data_type: "str" }, display_name: { label: "Display name", data_type: "str" } } }, diagnoses: [], environments: [], rules: [], history: [],
    } }
    if (path === "/api/v1/admin/assay-setups/setup-one" && route.request().method() === "PUT") {
      expect(route.request().headers()["x-edit-session"]).toBe(owner)
      savedName = route.request().postDataJSON().content.panel.display_name
      revision++
      return { json: { ...setup, revision } }
    }
  })
  await install(page)
  await page.goto("/admin/assay-setups?setup=setup-one")
  await expect(page.getByRole("button", { name: "Save and continue" })).toBeVisible()
  const otherContext = await browser.newContext()
  try {
    const other = await otherContext.newPage()
    await install(other)
    await other.goto("/admin/assay-setups?setup=setup-one")
    await expect(other.getByText(/editor.one is editing this document/)).toBeVisible()
    await expect(other.getByRole("button", { name: "Save and continue" })).toHaveCount(0)
    await page.getByLabel("Display name", { exact: true }).fill("Reviewed shared draft")
    await page.getByRole("button", { name: "Save and continue" }).click()
    await expect.poll(() => revision).toBe(2)
    await page.getByRole("button", { name: "New assay setup" }).click()
    await expect.poll(() => owner).toBeNull()
    await other.getByRole("button", { name: "Reload document" }).click()
    await expect(other.getByRole("button", { name: "Save and continue" })).toBeVisible()
    await expect(other.getByLabel("Display name", { exact: true })).toHaveValue("Reviewed shared draft")
  } finally {
    await otherContext.close()
  }
})
