import { expect, test } from "@playwright/test"

test("deployment serves login and public catalog through its configured prefix", async ({ page }) => {
  await page.goto("login")
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible()

  await page.goto("public/catalog")
  await expect(page.getByRole("heading", { name: /Assay Catalog/i })).toBeVisible()
})

test("API resource navigation opens and scrolls to the selected endpoints", async ({ page }) => {
  await page.goto("api/v1/docs")
  const navigation = page.getByRole("navigation", { name: "Endpoint groups" })
  const resource = navigation.getByRole("link", { name: /^Clinical Samples/ })
  const heading = page.locator('.opblock-tag[data-tag="Clinical Samples"]')
  await expect(heading).toBeVisible()
  await heading.getByRole("button", { name: "Collapse operation" }).click()
  await expect(heading).toHaveAttribute("data-is-open", "false")
  await resource.click()
  await expect(heading).toHaveAttribute("data-is-open", "true")
  await expect(heading).toBeInViewport()
  await expect(resource).toHaveAttribute("aria-current", "location")

  // A repeated selection must work even when the URL fragment is unchanged.
  await page.evaluate(() => window.scrollTo(0, 0))
  await resource.click()
  await expect(heading).toBeInViewport()

  await page.getByPlaceholder("Filter by tag").fill("Authentication")
  await expect(heading).toHaveCount(0)
  await resource.click()
  await expect(heading).toBeInViewport()
  await expect(heading).toHaveAttribute("data-is-open", "true")
  await expect(page.getByPlaceholder("Filter by tag")).toHaveValue("")

  await page.setViewportSize({ width: 390, height: 844 })
  await resource.focus()
  await page.keyboard.press("Enter")
  await expect(heading).toBeInViewport()
})

test("public matrix loads from the deployed API", async ({ page }) => {
  await page.goto("public/matrix")
  await expect(page.getByText("Assay Catalog - Gene Coverage Matrix")).toBeVisible()
  await expect(page.getByLabel("Gene search")).toBeVisible()
})

test("API explorer groups endpoints and keeps the overview collapsible", async ({ page }) => {
  await page.goto("api/v1/docs")
  const navigation = page.getByRole("navigation", { name: "Endpoint groups" })
  await expect(navigation.getByRole("link").first()).toBeVisible()
  await expect(page.locator("#endpoint-count")).toHaveText(/\d+ endpoints/)
  const overview = page.locator(".api-overview")
  await expect(overview.getByRole("heading", { name: "About Coyote3" })).toBeVisible()
  await expect(overview).toContainText("Section for Molecular Diagnostics (SMD), Lund")
  await expect(overview).toHaveAttribute("open")
  await expect(page.locator("#api-content .api-overview")).toHaveCount(0)
  expect(await overview.evaluate((element) => Boolean(
    element.compareDocumentPosition(document.getElementById("api-content")!) & Node.DOCUMENT_POSITION_FOLLOWING,
  ))).toBe(true)
  await overview.locator(":scope > summary").click()
  await expect(overview).not.toHaveAttribute("open")
  await overview.locator(":scope > summary").click()
  await expect(page.getByRole("heading", { name: "Authentication and access" })).toBeVisible()
  await page.getByLabel("Find a resource").fill("no-such-resource-123")
  await expect(page.getByText("No matching resources.")).toBeVisible()
  await page.getByLabel("Find a resource").fill("")
  const first = navigation.getByRole("link").first()
  await first.click()
  await expect(first).toHaveAttribute("aria-current", "location")
  await expect(page.locator("#docs-error")).toBeHidden()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test("API reference introduces Coyote3 and its clinical reporting context", async ({ page }) => {
  await page.goto("api/v1/redoc")
  const reference = page.locator("#api-renderer")
  await expect(reference).toContainText("Section for Molecular Diagnostics (SMD), Lund", { timeout: 30_000 })
  await expect(reference).toContainText("Saved reports retain finding snapshots")
  await expect(page.locator("#docs-error")).toBeHidden()
})
