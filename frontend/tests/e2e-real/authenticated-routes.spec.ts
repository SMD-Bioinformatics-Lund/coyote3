import { expect, test } from "@playwright/test"

const username = process.env.COYOTE3_E2E_USERNAME
const password = process.env.COYOTE3_E2E_PASSWORD
const dnaSample = process.env.COYOTE3_E2E_DNA_SAMPLE
const rnaSample = process.env.COYOTE3_E2E_RNA_SAMPLE

async function signIn(page: import("@playwright/test").Page) {
  test.skip(!username || !password, "Set controlled deployment smoke credentials.")
  await page.goto("login")
  await page.getByRole("button", { name: "Local Account" }).click()
  await page.getByLabel("Username").fill(username!)
  await page.getByLabel("Password").fill(password!)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
}

test("authenticated deployment opens dashboard and sample workspace", async ({ page }) => {
  await signIn(page)
  await page.getByRole("link", { name: "Open samples" }).click()
  await expect(page.getByRole("heading", { name: "Samples" })).toBeVisible()
})

test("DNA validation sample exposes its configured analysis and report preview", async ({ page }) => {
  test.skip(!dnaSample, "COYOTE3_E2E_DNA_SAMPLE must name a controlled DNA validation sample.")
  await signIn(page)
  await page.goto(`samples/${encodeURIComponent(dnaSample!)}`)
  await expect(page.getByRole("button", { name: /Somatic SNVs/i })).toBeVisible()
  await page.getByRole("button", { name: /Somatic SNVs/i }).click()
  await expect(page.getByText(/variants/i).first()).toBeVisible()
  await page.getByRole("button", { name: "Reports" }).click()
  await expect(page.getByText(/Rendered report preview/i)).toBeVisible()
})

test("RNA validation sample exposes fusion and configured RNA result tabs", async ({ page }) => {
  test.skip(!rnaSample, "COYOTE3_E2E_RNA_SAMPLE must name a controlled RNA validation sample.")
  await signIn(page)
  await page.goto(`samples/${encodeURIComponent(rnaSample!)}`)
  await expect(page.getByRole("button", { name: "Fusions" })).toBeVisible()
  await page.getByRole("button", { name: "Fusions" }).click()
  await expect(page.getByText(/fusions/i).first()).toBeVisible()
})

test("authorized operator can inspect application controls through the proxy", async ({ page }) => {
  await signIn(page)
  await page.goto("admin/controls")
  await expect(page.getByRole("heading", { name: "Application Controls" })).toBeVisible()
  await expect(page.getByText("Observed Runtime State")).toBeVisible()
})
