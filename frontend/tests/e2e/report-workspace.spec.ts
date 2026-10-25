import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const view of [
  { name: "desktop", width: 1440, height: 1000, theme: "light" },
  { name: "wide desktop", width: 2560, height: 1440, theme: "light" },
  { name: "dark desktop", width: 1440, height: 1000, theme: "dark" },
  { name: "tablet", width: 900, height: 1000, theme: "light" },
  { name: "mobile", width: 390, height: 844, theme: "light" },
]) {
  test(`report review remains usable on ${view.name}`, async ({ page }) => {
    await page.setViewportSize({ width: view.width, height: view.height })
    const previewRequests: string[] = []
    await installApiFixtures(page, (path, url) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "demo", role: "superuser", roles: ["superuser"],
        permissions: [], access_level: 100000, ui_settings: { theme: view.theme },
      } }
      if (path.endsWith("/edit-context")) return { json: {
        sample: { name: "SYNTHETIC_REPORT", case_id: "SYNTHETIC_CASE", asp_id: "demo",
          asp_category: "dna", analysis_intents: ["somatic"], data_counts: { snvs: 1 } },
        analysis_sections: ["SNV"],
      } }
      if (path.endsWith("/reports/dna/preview")) {
        previewRequests.push(url.search)
        const included = url.searchParams.get("include_snapshot") === "true"
        return { json: {
          sample: { name: "SYNTHETIC_REPORT" },
          meta: { template_status: { has_html: true }, snapshot_count: included ? 3 : 0,
            preview_fingerprint: "synthetic-preview" },
          report: {
            html: "<html><body><h1>Synthetic report</h1><table style='width:580px'><tr><td>Test finding</td></tr></table><div style='height:1000px'>Synthetic document content</div></body></html>",
            snapshot_rows: included
              ? [
                { analysis_type: "HRD", biomarker: "HRD", result: { HRD: { tai: 2, hrd: 3, lst: 4, sum: 9 } } },
                { analysis_type: "MSI", biomarker: "MSI", result: { MSIS: { per: 0, som: 0, tot: 100 }, MSIP: { per: 1, som: 1, tot: 100 } } },
                { analysis_type: "TMB", biomarker: "TMB", result: { TMB: { value: 12.4, unit: "mut/Mb" } } },
              ]
              : [],
          },
        } }
      }
    })
    await page.goto("/samples/SYNTHETIC_REPORT?tab=reports")
    await expect(page.getByRole("heading", { name: "Review summary" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Save report", exact: true })).toBeEnabled()
    await expect(page.frameLocator('iframe[title="Report preview"]').getByText("Test finding")).toBeAttached()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const documentBox = await page.getByRole("region", { name: "Rendered report preview" }).boundingBox()
    const review = await page.getByRole("complementary", { name: "Report review" }).boundingBox()
    const biomarkerCards = await page.locator(".report-biomarker-section").evaluateAll((cards) =>
      cards.map((card) => ({ width: card.getBoundingClientRect().width, y: card.getBoundingClientRect().y })))
    expect(biomarkerCards).toHaveLength(3)
    expect(await page.locator(".report-workspace").evaluate((element) => {
      const style = getComputedStyle(element)
      const reference = document.createElement("div")
      reference.style.backgroundColor = "var(--paper-raised)"
      element.append(reference)
      const matchesSharedBackground = style.backgroundColor === getComputedStyle(reference).backgroundColor
      reference.remove()
      return { sharedCard: element.classList.contains("glass-card"),
        background: matchesSharedBackground,
        border: style.borderWidth }
    })).toEqual({ sharedCard: true, background: true, border: "1px" })
    for (const selector of [".report-document", ".report-inspector"]) {
      expect(await page.locator(selector).evaluate((element) => ({
        border: getComputedStyle(element).borderWidth,
        padding: getComputedStyle(element).padding,
      }))).toEqual({ border: "1px", padding: "0px" })
    }
    const headerBackgrounds = await page.locator(".report-document-caption, .report-inspector-heading")
      .evaluateAll((elements) => elements.map((element) => getComputedStyle(element).backgroundColor))
    expect(headerBackgrounds).toHaveLength(2)
    expect(headerBackgrounds[0]).toBe(headerBackgrounds[1])
    expect(headerBackgrounds[0]).not.toBe("rgba(0, 0, 0, 0)")
    const cardWidthLimit = await page.evaluate(() =>
      24 * Number.parseFloat(getComputedStyle(document.documentElement).fontSize))
    expect(biomarkerCards.every((card) => card.width <= cardWidthLimit + 1)).toBe(true)
    if (view.theme === "light") {
      const levels = await page.evaluate(() => {
        const probe = document.createElement("canvas")
        probe.width = probe.height = 1
        const ctx = probe.getContext("2d")!
        const luminance = (color: string) => {
          ctx.clearRect(0, 0, 1, 1)
          ctx.fillStyle = color
          ctx.fillRect(0, 0, 1, 1)
          const rgb = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map((value) => {
            const channel = value / 255
            return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4
          })
          return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
        }
        const canvasStyle = getComputedStyle(document.querySelector(".app-chrome-bg")!)
        const stops = canvasStyle.backgroundImage.match(/(?:oklch|oklab|rgb|color)\([^)]+\)/g)
          ?? [canvasStyle.backgroundColor]
        const canvasLevels = stops.map(luminance)
        return { canvas: Math.max(...canvasLevels), gradient: canvasStyle.backgroundImage }
      })
      // The shared parent card sits above the subdued app canvas.
      expect(levels.canvas).toBeLessThan(.80)
      expect(levels.gradient).toContain("linear-gradient")
    }
    if (view.width >= 2500) {
      expect(biomarkerCards.every((card) => Math.abs(card.y - biomarkerCards[0].y) < 1)).toBe(true)
    }
    if (view.width > 1120) {
      expect(review!.x).toBeGreaterThan(documentBox!.x)
      expect(review!.height).toBeLessThan(documentBox!.height)
      const reportWidthLimit = await page.evaluate(() =>
        52 * Number.parseFloat(getComputedStyle(document.documentElement).fontSize))
      expect(documentBox!.width).toBeLessThanOrEqual(reportWidthLimit + 1)
      const paper = await page.getByTitle("Report preview", { exact: true }).boundingBox()
      expect(Math.abs(paper!.x - documentBox!.x - 1)).toBeLessThan(1)
      expect(Math.abs(documentBox!.width - paper!.width - 2)).toBeLessThan(1)
    } else {
      expect(review!.y).toBeGreaterThanOrEqual(documentBox!.y + documentBox!.height - 1)
      if (view.width < 600) {
        const scrollRegion = page.getByRole("region", { name: "Report document", exact: true })
        expect(await scrollRegion.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
      }
    }
    await page.getByRole("switch", { name: "Include finding snapshot" }).uncheck()
    await expect(page.getByText("The finding snapshot is turned off for this preview.")).toBeVisible()
    expect(previewRequests.some((search) => search.includes("include_snapshot=false"))).toBe(true)
    expect(previewRequests.every((search) => search.includes("save=false"))).toBe(true)
    await page.getByRole("button", { name: "Save report", exact: true }).click()
    await expect(page.getByRole("alertdialog")).toContainText("Confirm report save")
    await expect(page.getByRole("button", { name: "Confirm save", exact: true })).toBeVisible()
  })
}
