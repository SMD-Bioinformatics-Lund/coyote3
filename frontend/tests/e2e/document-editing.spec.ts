import { expect, test, type Page } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test.use({ timezoneId: "Europe/Stockholm" })

test("a second editor is read-only until the first editor leaves", async ({ page, browser }) => {
  // HTTP intranet origins expose getRandomValues but not randomUUID.
  const httpCrypto = () => Object.defineProperty(window.crypto, "randomUUID", { value: undefined, configurable: true })
  await page.addInitScript(httpCrypto)
  let owner: string | null = null
  let savedName = "Synthetic assay"
  let revision = 1
  const install = async (target: Page) => installApiFixtures(target, (path, _url, route) => {
    if (path.startsWith("/api/v1/editing/")) {
      const editor = route.request().postDataJSON().editor_id as string
      if (path.endsWith("/release") && owner === editor) owner = null
      if (path.endsWith("/acquire") && !owner) owner = editor
      return { json: { owned: owner === editor, owner: "editor.one", expires_at: new Date(Date.now() + 90_000).toISOString(), renew_after_seconds: 30 } }
    }
    const panel = { asp_id: "synthetic", asp_group: "demo", display_name: savedName, version: revision, is_active: true }
    if (path === "/api/v1/resources/asp/synthetic/context") return { json: {
      panel, form: { fields: { display_name: { label: "Display name", display_type: "input", data_type: "str", value: savedName } } },
    } }
    if (path === "/api/v1/resources/asp/synthetic" && route.request().method() === "PUT") {
      expect(route.request().headers()["x-edit-session"]).toBe(owner)
      savedName = route.request().postDataJSON().config.display_name
      revision++
      return { json: { meta: { revision: { new_version: revision } } } }
    }
  })
  await install(page)
  await page.goto("/admin/asp/synthetic/edit")
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible()
  const otherContext = await browser.newContext()
  try {
    const other = await otherContext.newPage()
    await other.addInitScript(httpCrypto)
    await install(other)
    await other.goto("/admin/asp/synthetic/edit")
    await expect(other.getByText(/editor.one is editing this document/)).toBeVisible()
    await expect(other.getByRole("button", { name: "Save", exact: true })).toHaveCount(0)
    await page.getByLabel("Display name", { exact: true }).fill("Updated synthetic assay")
    await page.getByRole("button", { name: "Save", exact: true }).click()
    await expect.poll(() => revision).toBe(2)
    await expect(page).toHaveURL(/\/admin\/asp$/)
    await expect.poll(() => owner).toBeNull()
    await other.getByRole("button", { name: "Reload document" }).click()
    await expect(other.getByRole("button", { name: "Save", exact: true })).toBeVisible()
    await expect(other.getByLabel("Display name", { exact: true })).toHaveValue("Updated synthetic assay")
  } finally {
    await otherContext.close()
  }
})
