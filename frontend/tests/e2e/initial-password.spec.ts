import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const { width, entry } of [
  { width: 1440, entry: "/profile" },
  { width: 390, entry: "/profile" },
  { width: 1440, entry: "/login" },
]) {
  test(`temporary credentials force password replacement from ${entry} at ${width}px`, async ({ page }, testInfo) => {
    let changed = false
    await page.setViewportSize({ width, height: 900 })
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/auth/whoami") return { json: { username: "operator", roles: ["sys_admin"], permissions: [], must_change_password: !changed } }
      if (path === "/api/v1/auth/password/change") {
        const body = route.request().postDataJSON()
        expect(body.new_password).toBe(body.confirm_password)
        changed = true
        return { json: { status: "ok" } }
      }
      if (path === "/api/v1/auth/providers") return { json: { providers: ["local"] } }
      if (path === "/api/v1/auth/sessions") return { json: { user: { must_change_password: true } } }
    })
    await page.goto(entry)
    if (entry === "/login") {
      await page.getByLabel("Username", { exact: true }).fill("operator")
      await page.getByLabel("Password", { exact: true }).fill("Temporary!123")
      await page.getByRole("button", { name: "Sign in", exact: true }).click()
    }
    await expect(page).toHaveURL(/\/change-password$/)
    await page.getByLabel("Current password", { exact: true }).fill("Temporary!123")
    await page.getByLabel("New password", { exact: true }).fill("Personal!12345")
    await page.getByLabel("Confirm new password", { exact: true }).fill("Mismatch!123")
    await expect(page.getByRole("button", { name: "Change password", exact: true })).toBeDisabled()
    await page.getByLabel("Confirm new password", { exact: true }).fill("Personal!12345")
    await page.screenshot({ path: testInfo.outputPath("password-change.png"), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole("button", { name: "Change password", exact: true }).click()
    await expect(page).toHaveURL(/\/login\?password=changed$/)
    await expect(page.getByRole("status").filter({ hasText: "Password changed." })).toHaveText("Password changed. Sign in with your new password.")
  })
}
