import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"] as const) {
  for (const width of [390, 1440]) {
    test(`personal access tokens: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      const secret = "coy3_service_SYNTHETIC_PERSONAL_TEST_ONLY"
      let saved: Record<string, unknown> | null = null
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "owner", roles: ["user"], permissions: ["internal.ingest:manage", "sample:edit:own", "internal.task:view"], ui_settings: { theme } } }
        if (path.endsWith("/auth/session")) return { json: { user: { username: "owner", roles: ["user"], auth_type: ["local"], permissions: ["internal.ingest:manage", "sample:edit:own", "internal.task:view"], asp_ids: ["assay_a"] } } }
        if (path.endsWith("/personal-tokens/options")) return { json: { owners: [], assays: [{ asp_id: "assay_a", name: "Assay A" }], environments: ["testing"], operations: ["sample_upload_async", "job_status"] } }
        if (path.endsWith("/personal-tokens/personal-id") && route.request().method() === "DELETE") {
          saved = { ...saved, revoked_at: new Date().toISOString() }
          return { json: saved }
        }
        if (path.endsWith("/personal-tokens")) {
          if (route.request().method() === "POST") {
            expect(route.request().postDataJSON()).toEqual({ name: "Personal pipeline", expires_hours: 720, operations: ["sample_upload_async", "job_status"], asp_ids: ["assay_a"], environments: ["testing"] })
            saved = { ...route.request().postDataJSON(), kind: "personal", owner: "owner", token_id: "personal-id", audience: "testing", expires_at: "2099-01-01T00:00:00Z", last_used_at: null, revoked_at: null }
            return { status: 201, json: { token: secret, metadata: saved } }
          }
          return { json: { items: saved ? [saved] : [] } }
        }
      })
      await page.goto("/profile")
      await page.getByRole("button", { name: "User menu for owner" }).click()
      await page.locator(".paper-menu").getByRole("link", { name: "Access tokens", exact: true }).click()
      await expect(page.getByRole("heading", { name: "Access tokens", exact: true })).toBeVisible()
      await expect(page.getByLabel("Owner", { exact: true })).toHaveCount(0)
      await page.getByLabel("Name", { exact: true }).fill("Personal pipeline")
      await page.getByLabel("Upload a background sample bundle", { exact: true }).check()
      await page.getByLabel("Read status and results of jobs submitted with this token").check()
      await page.getByLabel("Assay A (assay_a)").check()
      await page.getByLabel("testing", { exact: true }).check()
      await page.getByRole("button", { name: "Create token", exact: true }).click()
      await expect(page.getByLabel("New personal token")).toHaveValue(secret)
      await page.getByRole("link", { name: "My account", exact: true }).click()
      await page.getByRole("link", { name: "Access tokens", exact: true }).click()
      await expect(page.getByLabel("New personal token")).toHaveCount(0)
      await page.getByRole("button", { name: "Revoke Personal pipeline" }).click()
      await page.getByRole("alertdialog").getByRole("button", { name: "Revoke token" }).click()
      await expect(page.getByText("Revoked", { exact: true })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await page.screenshot({ path: testInfo.outputPath(`personal-tokens-${theme}-${width}.png`), fullPage: true })
    })

    test(`managed service tokens: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      const secret = "coy3_service_SYNTHETIC_BROWSER_TEST_ONLY"
      let saved: Record<string, unknown> | null = null
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "issuer", roles: ["sysadmin"], permissions: ["ingest.token:issue"], ui_settings: { theme } } }
        if (path.endsWith("/service-tokens/options")) return { json: { owners: [{ username: "owner", name: "Pipeline Owner" }], assays: [{ asp_id: "assay_a", name: "Assay A" }], environments: ["testing", "production"], operations: ["sample_bundle", "sample_upload", "sample_bundle_async", "sample_upload_async", "job_status"] } }
        if (path.endsWith("/service-tokens/synthetic-id") && route.request().method() === "DELETE") {
          saved = { ...saved, revoked_at: new Date().toISOString(), revoked_by: "issuer" }
          return { json: saved }
        }
        if (path.endsWith("/service-tokens")) {
          if (route.request().method() === "POST") {
            expect(route.request().postDataJSON()).toEqual({ name: "Synthetic pipeline", owner: "owner", expires_hours: 720, operations: ["sample_upload"], asp_ids: ["assay_a"], environments: ["testing"] })
            saved = { ...route.request().postDataJSON(), kind: "service", token_id: "synthetic-id", audience: "testing", created_by: "issuer", created_at: new Date().toISOString(), expires_at: "2099-01-01T00:00:00Z", last_used_at: null, revoked_at: null }
            return { status: 201, json: { token: secret, metadata: saved } }
          }
          return { json: { items: saved ? [saved] : [] } }
        }
      })
      await page.goto("/admin")
      await page.getByRole("region", { name: "Identity and access" }).getByRole("link", { name: /Service tokens/ }).click()
      await expect(page.getByRole("heading", { name: "Service tokens", exact: true })).toBeVisible()
      await expect(page.getByRole("button", { name: "Create token", exact: true })).toBeDisabled()
      await page.getByLabel("Name", { exact: true }).fill("Synthetic pipeline")
      await page.getByLabel("Owner", { exact: true }).selectOption("owner")
      await page.getByLabel("Assay A (assay_a)", { exact: true }).check()
      await page.getByLabel("testing", { exact: true }).check()
      await page.getByRole("button", { name: "Create token", exact: true }).click()
      await expect(page.getByLabel("New service token")).toHaveValue(secret)
      await page.getByRole("button", { name: "Dismiss secret" }).click()
      await expect(page.getByLabel("New service token")).toHaveCount(0)
      await page.getByRole("button", { name: "Revoke Synthetic pipeline" }).click()
      const confirmation = page.getByRole("alertdialog")
      await expect(confirmation.getByRole("button", { name: "Cancel" })).toBeFocused()
      await confirmation.getByRole("button", { name: "Revoke token" }).click()
      await expect(page.getByText("Revoked", { exact: true })).toBeVisible()
      await expect(page.getByRole("button", { name: "Revoke Synthetic pipeline" })).toBeDisabled()
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(secret)
      await page.screenshot({ path: testInfo.outputPath(`service-tokens-${theme}-${width}.png`), fullPage: true })
    })
  }
}
