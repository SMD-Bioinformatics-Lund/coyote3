import { expect, test } from "@playwright/test"

const username = process.env.COYOTE3_E2E_USERNAME
const password = process.env.COYOTE3_E2E_PASSWORD

test("authenticated deployment opens dashboard and sample workspace", async ({ page }) => {
  test.skip(!username || !password, "Set COYOTE3_E2E_USERNAME and COYOTE3_E2E_PASSWORD to run authenticated smoke tests.")

  await page.goto("login")
  await page.getByRole("button", { name: "Local Account" }).click()
  await page.getByLabel("Username").fill(username!)
  await page.getByLabel("Password").fill(password!)
  await page.getByRole("button", { name: "Sign in" }).click()

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  await page.getByRole("link", { name: "Open samples" }).click()
  await expect(page.getByRole("heading", { name: "Samples" })).toBeVisible()
})
