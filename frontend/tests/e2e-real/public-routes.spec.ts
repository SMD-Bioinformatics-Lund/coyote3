import { expect, test } from "@playwright/test"

test("deployment serves login and public catalog through its configured prefix", async ({ page }) => {
  await page.goto("login")
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible()

  await page.goto("public/catalog")
  await expect(page.getByRole("heading", { name: /Assay Catalog/i })).toBeVisible()
})

test("public matrix loads from the deployed API", async ({ page }) => {
  await page.goto("public/matrix")
  await expect(page.getByText("Assay Catalog - Gene Coverage Matrix")).toBeVisible()
  await expect(page.getByLabel("Gene search")).toBeVisible()
})
