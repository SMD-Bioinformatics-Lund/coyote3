import { expect, test } from "@playwright/test"
import { readFile } from "node:fs/promises"

const username = process.env.COYOTE3_E2E_USERNAME
const password = process.env.COYOTE3_E2E_PASSWORD
const dnaSample = process.env.COYOTE3_E2E_DNA_SAMPLE
const rnaSample = process.env.COYOTE3_E2E_RNA_SAMPLE

async function signIn(page: import("@playwright/test").Page) {
  test.skip(!username || !password, "Set controlled deployment smoke credentials.")
  const providersLoaded = page.waitForResponse(response =>
    response.url().endsWith("/api/v1/auth/providers") && response.ok(),
  )
  await page.goto("login")
  await providersLoaded
  const localAccount = page.getByRole("button", { name: "Local Account" })
  const usernameInput = page.getByLabel("Username")
  await expect(localAccount.or(usernameInput).first()).toBeVisible()
  if (await localAccount.isVisible()) await localAccount.click()
  await usernameInput.fill(username!)
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
  await page.getByRole("tab", { name: "Modern", exact: true }).click()
  await expect(page.getByRole("tab", { name: /Somatic SNVs/i })).toBeVisible()
  await page.getByRole("tab", { name: /Somatic SNVs/i }).click()
  await expect(page.getByText(/variants/i).first()).toBeVisible()
  await page.getByRole("tab", { name: "Reports", exact: true }).click()
  await expect(page.getByRole("region", { name: "Rendered report preview" })).toBeVisible()
})

test("RNA validation sample exposes fusion and configured RNA result tabs", async ({ page }) => {
  test.skip(!rnaSample, "COYOTE3_E2E_RNA_SAMPLE must name a controlled RNA validation sample.")
  await signIn(page)
  await page.goto(`samples/${encodeURIComponent(rnaSample!)}`)
  await page.getByRole("tab", { name: "Modern", exact: true }).click()
  await expect(page.getByRole("tab", { name: "Fusions", exact: true })).toBeVisible()
  await page.getByRole("tab", { name: "Fusions", exact: true }).click()
  await expect(page.getByText(/fusions/i).first()).toBeVisible()
})

test("authorized operator can inspect application controls through the proxy", async ({ page }) => {
  await signIn(page)
  await page.goto("admin/controls")
  await expect(page.getByRole("heading", { name: "Application Controls" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Observed Runtime State" })).toBeVisible({ timeout: 30_000 })
})

for (const [analyte, sampleId] of [["dna", dnaSample], ["rna", rnaSample]] as const) {
  test(`${analyte} trial previews and downloads one temporary HTML/PDF pair`, async ({ page }) => {
    test.skip(!sampleId, "A controlled synthetic sample is required.")
    await signIn(page)
    await page.goto(`samples/${encodeURIComponent(sampleId!)}`)
    await page.getByRole("tab", { name: "Modern", exact: true }).click()
    await page.getByRole("tab", { name: "Reports", exact: true }).click()
    const libraryPath = `api/v1/reports?search=${encodeURIComponent(sampleId!)}`
    const savedBefore = await page.request.get(libraryPath)
    expect(savedBefore.ok()).toBe(true)
    const writes: string[] = []
    page.on("request", request => {
      if (request.url().includes("/reports/") && request.method() !== "GET") writes.push(request.url())
    })
    await page.getByRole("button", { name: "Try new report", exact: true }).click()
    const frame = page.frameLocator('iframe[title="New report HTML preview"]')
    await expect(frame.getByText("TRY NEW REPORT · TEMPORARY PREVIEW")).toBeVisible()
    await expect(page.getByRole("button", { name: "Save report", exact: true })).toHaveCount(0)
    const htmlDownload = page.waitForEvent("download")
    await page.getByRole("button", { name: "Download HTML", exact: true }).click()
    const html = await htmlDownload
    expect(html.suggestedFilename()).toBe(`coyote3_${analyte}_report_trial.html`)
    const htmlContent = await readFile((await html.path())!, "utf-8")
    expect(htmlContent).toContain('<style id="modern-report-style">')
    expect(htmlContent).toContain(sampleId!)
    await page.getByRole("tab", { name: "PDF preview", exact: true }).click()
    await expect(page.getByTitle("New report PDF preview", { exact: true })).toHaveAttribute("src", /^blob:/)
    const pdfDownload = page.waitForEvent("download")
    await page.getByRole("button", { name: "Download PDF", exact: true }).click()
    const pdf = await pdfDownload
    expect(pdf.suggestedFilename()).toBe(`coyote3_${analyte}_report_trial.pdf`)
    expect((await readFile((await pdf.path())!)).subarray(0, 5).toString()).toBe("%PDF-")
    expect(writes).toEqual([])
    const savedAfter = await page.request.get(libraryPath)
    expect(savedAfter.status()).toBe(savedBefore.status())
    expect(await savedAfter.json()).toEqual(await savedBefore.json())
    await page.getByRole("button", { name: "Current report", exact: true }).click()
    await expect(page.getByRole("region", { name: "Rendered report preview" })).toBeVisible()
  })
}
