import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

/** A complete one-page synthetic PDF with valid object offsets and no clinical data. */
function syntheticPdf() {
  const text = "BT /F1 14 Tf 25 200 Td (Synthetic PDF preview) Tj ET"
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
  ]
  let pdf = "%PDF-1.4\n"
  const offsets = [0]
  objects.forEach((object, index) => {
    offsets.push(pdf.length)
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`
  })
  const xref = pdf.length
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}`
  pdf += `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(pdf)
}

for (const supported of [true, false]) {
  test(`PDF previews recover and offer usable controls with embedded support ${supported}`, async ({ page }, testInfo) => {
    await page.addInitScript(enabled => {
      Object.defineProperty(Navigator.prototype, "pdfViewerEnabled", { configurable: true, get: () => enabled })
    }, supported)
    const pdf = syntheticPdf()
    let requests = 0
    await installApiFixtures(page, path => {
      if (path.endsWith("/edit-context")) return { json: {
        sample: { name: "SYNTHETIC_REPORT", asp_category: "dna", analysis_intents: ["somatic"] },
        analysis_sections: ["SNV"],
      } }
      if (path.endsWith("/reports/dna/preview")) return { json: {
        sample: { name: "SYNTHETIC_REPORT" },
        meta: { template_status: { has_html: true }, preview_fingerprint: "synthetic-preview" },
        report: { html: "<h1>Synthetic report</h1>", snapshot_rows: [] },
      } }
      if (path.endsWith("/reports/dna/try-new")) return { json: {
        html: "<h1>Synthetic modern report</h1>", pdf_base64: pdf.toString("base64"),
        filename: "synthetic-modern", snapshot_count: 0,
      } }
    })
    await page.route("**/reports/dna/preview/pdf?**", route => {
      requests++
      return route.fulfill(requests === 1
        ? { body: "<html>Interrupted PDF response</html>", contentType: "text/html" }
        : { body: pdf, contentType: "application/pdf" })
    })
    await page.route("**/samples/SYNTHETIC_REPORT?tab=reports", async route => {
      const response = await route.fetch()
      await route.fulfill({ response, headers: {
        ...response.headers(),
        "content-security-policy": "default-src 'self'; object-src 'none'; frame-src 'self' blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws:; font-src 'self' data:",
      } })
    })
    await page.goto("/samples/SYNTHETIC_REPORT?tab=reports")
    await page.getByRole("tab", { name: "PDF preview", exact: true }).click()
    await expect(page.getByRole("alert")).toContainText("invalid or incomplete")
    await page.getByRole("button", { name: "Retry PDF preview" }).click()
    const open = page.getByRole("link", { name: "Open PDF", exact: true })
    await expect(open).toHaveAttribute("href", /^blob:/)
    const original = await open.getAttribute("href")
    if (supported) {
      await expect(page.getByTitle("Report PDF preview")).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath("report-pdf.png"), fullPage: true })
    }
    else await expect(page.getByRole("status").filter({ hasText: "does not support embedded" })).toBeVisible()
    await page.getByRole("button", { name: "Reload PDF viewer" }).click()
    await expect(open).not.toHaveAttribute("href", original!)
    await page.getByRole("tab", { name: "HTML preview", exact: true }).click()
    await page.getByRole("tab", { name: "PDF preview", exact: true }).click()
    await expect(open).toHaveAttribute("href", /^blob:/)
    const downloaded = page.waitForEvent("download")
    await page.getByRole("button", { name: "Download this PDF" }).click()
    expect((await downloaded).suggestedFilename()).toBe("SYNTHETIC_REPORT_dna_preview.pdf")
    expect(requests).toBe(2)
    await page.getByRole("tab", { name: "Legacy format", exact: true }).click()
    await expect(page.getByRole("heading", { name: "Legacy report preview" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Open PDF" })).toHaveAttribute("href", /^blob:/)
    if (supported) await expect(page.getByTitle("Report PDF preview")).toBeVisible()
    else await expect(page.getByRole("status").filter({ hasText: "does not support embedded" })).toBeVisible()
    expect(requests).toBe(3)
  })
}
