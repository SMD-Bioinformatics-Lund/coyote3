import { expect, test } from "@playwright/test"
import { readFileSync } from "node:fs"
import { readFile } from "node:fs/promises"
import type { ReportPreviewPayload } from "../../src/lib/generated"
import { reportPackageVersion } from "./support/deployment-settings"

import { signIn, state } from "./support/session"

const dnaSample = state.dnaSample
const rnaSample = state.rnaSample
const expectedReportVersion = reportPackageVersion(
  readFileSync(new URL("../../../core/pyproject.toml", import.meta.url), "utf-8"),
)

test("authenticated deployment opens dashboard and sample workspace", async ({ page }) => {
  await signIn(page)
  await page.getByRole("link", { name: "Open samples" }).click()
  await expect(page.getByRole("heading", { name: "Samples" })).toBeVisible()
})

test("DNA validation sample exposes its configured analysis and report preview", async ({ page }) => {
  await signIn(page)
  await page.goto(`samples/${encodeURIComponent(dnaSample!)}`)
  await page.getByRole("tab", { name: "Modern", exact: true }).click()
  const variants = page.getByRole("tab", { name: /^(?:Somatic |Germline )?SNVs$/ }).first()
  await expect(variants).toBeVisible()
  await variants.click()
  await expect(page.getByText(/variants/i).first()).toBeVisible()
  await page.getByRole("tab", { name: "Reports", exact: true }).click()
  await expect(page.getByRole("region", { name: "Rendered report preview" })).toBeVisible()
})

test("RNA validation sample exposes fusion and configured RNA result tabs", async ({ page }) => {
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
  test(`${analyte} smd-reports previews download without issuing a report`, async ({ page }) => {
    await signIn(page)
    const libraryPath = `api/v1/reports?search=${encodeURIComponent(sampleId!)}`
    const savedBefore = await page.request.get(libraryPath)
    expect(savedBefore.ok()).toBe(true)
    const writes: string[] = []
    page.on("request", request => {
      const url = new URL(request.url())
      if (/\/reports(?:\/|$)/.test(url.pathname) && (
        !["GET", "HEAD", "OPTIONS"].includes(request.method()) || url.searchParams.get("save") === "true"
      )) writes.push(request.url())
    })
    await page.goto(`samples/${encodeURIComponent(sampleId!)}`)
    await page.getByRole("tab", { name: "Modern", exact: true }).click()
    const previewLoaded = page.waitForResponse(response =>
      new URL(response.url()).pathname.endsWith(`/reports/${analyte}/preview`) && response.request().method() === "GET",
    )
    await page.getByRole("tab", { name: "Reports", exact: true }).click()
    const previewResponse = await previewLoaded
    expect(previewResponse.ok()).toBe(true)
    const preview = await previewResponse.json() as ReportPreviewPayload
    expect(preview.meta?.template_status?.has_html).toBe(true)
    expect(preview.meta?.preview_fingerprint).toBeTruthy()
    const sampleName = preview.sample?.name || sampleId!
    const document = page.getByRole("region", { name: "Rendered report preview", exact: true })
    await expect(document).toBeVisible()
    await expect(document.getByRole("heading", { name: `${analyte.toUpperCase()} report`, exact: true })).toBeVisible()
    await expect(document.getByText(sampleName, { exact: true })).toBeVisible()
    const formats = document.getByRole("tablist", { name: "Report preview format" })
    await expect(formats.getByRole("tab")).toHaveText(["HTML preview", "PDF preview"])
    await expect(formats.getByRole("tab", { name: "HTML preview", exact: true })).toHaveAttribute("aria-selected", "true")
    const frame = page.frameLocator('iframe[title="Report preview"]')
    await expect(frame.getByText("PREVIEW · UNSAVED REPORT")).toBeVisible()
    await expect(frame.locator('.report-metadata:visible')).toHaveCount(1)
    await expect(frame.locator('meta[name="smd-reports:package_version"]')).toHaveAttribute("content", expectedReportVersion)
    const htmlDownload = page.waitForEvent("download")
    await page.getByRole("button", { name: "Download HTML", exact: true }).click()
    const html = await htmlDownload
    expect(html.suggestedFilename()).toBe(`${sampleName}_${analyte}_preview.html`)
    const htmlContent = await readFile((await html.path())!, "utf-8")
    expect(htmlContent).toBe(preview.report?.html)
    await page.getByRole("tab", { name: "PDF preview", exact: true }).click()
    await expect(page.getByRole("link", { name: "Open PDF", exact: true })).toHaveAttribute("href", /^blob:/)
    if (await page.evaluate(() => navigator.pdfViewerEnabled !== false)) {
      await expect(page.getByTitle("Report PDF preview", { exact: true })).toHaveAttribute("src", /^blob:/)
    } else {
      await expect(page.getByRole("status").filter({ hasText: "This browser does not support embedded PDF previews." })).toBeVisible()
    }
    const pdfDownload = page.waitForEvent("download")
    await page.getByRole("button", { name: "Download PDF", exact: true }).click()
    const pdf = await pdfDownload
    expect(pdf.suggestedFilename()).toBe(`${sampleName}_${analyte}_preview.pdf`)
    expect((await readFile((await pdf.path())!)).subarray(0, 5).toString()).toBe("%PDF-")
    await formats.getByRole("tab", { name: "HTML preview", exact: true }).click()
    await expect(frame.locator('meta[name="smd-reports:package_version"]')).toHaveAttribute("content", expectedReportVersion)
    expect(writes).toEqual([])
    const savedAfter = await page.request.get(libraryPath)
    expect(savedAfter.status()).toBe(savedBefore.status())
    expect(await savedAfter.json()).toEqual(await savedBefore.json())
  })
}
