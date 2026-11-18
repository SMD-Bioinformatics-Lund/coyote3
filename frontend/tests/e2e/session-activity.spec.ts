import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("superusers can refresh login counts in user administration", async ({ page }) => {
  let signedInUsers = 2
  await installApiFixtures(page, path => {
    if (path === "/api/v1/users") return { json: { users: [], roles: {} } }
    if (path === "/api/v1/users/session-activity") return { json: {
      signed_in_users: signedInUsers, active_sessions: 3, recently_active_users: 1,
      recent_activity_seconds: 300, observed_at: new Date().toISOString(),
    } }
  })
  await page.goto("/admin/users")
  const activity = page.getByRole("region", { name: "Login activity" })
  await expect(activity.getByText("2", { exact: true })).toBeVisible()
  signedInUsers = 1
  await activity.getByRole("button", { name: "Refresh", exact: true }).click()
  await expect(activity.getByText("2", { exact: true })).toHaveCount(0)
  await expect(activity.getByText("1", { exact: true })).toHaveCount(2)
})

test("regular administrators never request superuser session statistics", async ({ page }) => {
  let requests = 0
  await installApiFixtures(page, path => {
    if (path === "/api/v1/auth/whoami") return { json: {
      username: "synthetic-admin", roles: ["sys_admin"], role: "sys_admin",
      permissions: ["user:list"], access_level: 100,
    } }
    if (path === "/api/v1/users") return { json: { users: [], roles: {} } }
    if (path === "/api/v1/users/session-activity") {
      requests += 1
      return { status: 403 }
    }
  })
  await page.goto("/admin/users")
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible()
  await expect(page.getByRole("region", { name: "Login activity" })).toHaveCount(0)
  expect(requests).toBe(0)
})
