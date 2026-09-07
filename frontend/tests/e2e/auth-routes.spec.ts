import { expect, test } from "@playwright/test"

test("login renders configured providers and reports failed sign-in", async ({ page }) => {
  await page.route("**/api/v1/auth/providers", async (route) => {
    await route.fulfill({ json: { providers: ["local", "ldap"] } })
  })
  await page.route("**/api/v1/auth/sessions", async (route) => {
    await route.fulfill({ status: 401, json: { error: "Invalid local credentials." } })
  })

  await page.goto("/login")
  await expect(page.getByRole("button", { name: "Local Account" })).toBeVisible()
  await page.getByLabel("Username").fill("clinical.user")
  await page.getByLabel("Password").fill("wrong-password")
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByText("Invalid local credentials.")).toBeVisible()
})

test("password reset route handles a successful API result", async ({ page }) => {
  await page.route("**/api/v1/auth/password/reset/request", async (route) => {
    await route.fulfill({ json: { status: "ok" } })
  })

  await page.goto("/forgot-password")
  await page.getByLabel("Username or email").fill("clinical.user")
  await page.getByRole("button", { name: "Request reset" }).click()
  await expect(page.getByText("If this account can reset its password")).toBeVisible()
})
