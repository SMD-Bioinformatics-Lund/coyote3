import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  test(`published diagnosis and assay discovery in ${theme} mode`, async ({ page }) => {
    await page.setViewportSize({ width: theme === "light" ? 1440 : 390, height: 900 })
    const panel = {
      offering_id: "breast-panel", title: "Breast panel", group_id: "solid", group_label: "Solid",
      diagnosis_id: "breast", diagnosis_label: "Breast", modality: "dna", family: "panel-dna",
      assay_id: "solid_GMSv3", assay_label: "Solid GMSv3", description: "Targeted clinical service",
      analysis: ["SNV", "CNV"], price: { amount: "100.00", currency: "EUR", kind: "fixed", conditions: "" },
      pricing_message: "Contact for pricing", turnaround: "14 days", input_material: ["DNA"],
      report_deliverables: ["PDF"], methodology: "Targeted sequencing",
      limitations: "Validated regions only", ordering_information: "Contact the center",
      gene_scopes: [{ list_id: "breast", label: "Breast genes", revision: 2, analysis: "SNV",
        genes: ["BRCA1"], excluded_gene_count: 1 },
      { list_id: "cnv", label: "CNV genes", revision: 1, analysis: "CNV", genes: ["MYC"], excluded_gene_count: 0 }],
    }
    const wgs = { ...panel, offering_id: "breast-wgs", title: "Breast WGS", family: "wgs",
      assay_id: "solid_wgs", assay_label: "Solid WGS",
      price: { ...panel.price, amount: "400.00", kind: "estimated" },
      gene_scopes: [{ ...panel.gene_scopes[0], genes: ["TP53"] }],
    }
    const rna = { ...panel, offering_id: "breast-rna", title: "Breast RNA", modality: "rna",
      family: "panel-rna", assay_id: "rna-panel", assay_label: "RNA panel", analysis: ["FUSION"] }
    const wts = { ...rna, offering_id: "breast-wts", title: "Breast WTS", family: "wts",
      assay_id: "rna-wts", assay_label: "RNA WTS" }
    await installApiFixtures(page, (path) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "viewer", role: "user", roles: ["user"], permissions: [], ui_settings: { theme },
      } }
      if (path === "/api/v1/public/assay-catalog/offerings") return { json: {
        version: 2, header: "Genomic test catalog", description: "Published services", offerings: [panel, wgs, rna, wts],
      } }
    })
    await page.route("**/api/v1/public/asp/solid_GMSv3/genes", route => route.fulfill({ json: { gene_details: [
      { hgnc_symbol: "BRCA1", hgnc_id: "HGNC:1100", gene_name: "BRCA1 DNA repair associated", chromosome: "17", locus: "17q21.31",
        refseq_mane_plus_clinical: ["NM_007294.4"], ensembl_mane_select: "ENST00000357654.9" },
      { hgnc_symbol: "MYC", hgnc_id: "HGNC:7553", gene_name: "MYC proto-oncogene", chromosome: "8" },
    ] } }))
    await page.goto("/public/catalog")
    await expect(page.getByRole("button", { name: "By Diagnosis" })).toHaveAttribute("aria-pressed", "true")
    await expect(page.getByRole("article")).toHaveCount(4)
    const positions = await page.getByRole("article").evaluateAll(elements =>
      elements.map(element => {
        const { top, left } = element.getBoundingClientRect()
        return { top, left }
      }),
    )
    if (theme === "light") {
      expect(new Set(positions.map(position => position.top)).size).toBe(1)
      expect(new Set(positions.map(position => position.left)).size).toBe(4)
    } else {
      expect(new Set(positions.map(position => position.left)).size).toBe(1)
    }
    const toolbar = page.getByRole("region", { name: "Find a genomic test" })
    expect(await toolbar.evaluate(element => getComputedStyle(element).backgroundImage)).toContain("linear-gradient")
    const dnaCard = page.locator('.catalog-service-card[data-modality="dna"]').first()
    const rnaCard = page.locator('.catalog-service-card[data-family="panel-rna"]')
    await expect(rnaCard).toBeVisible()
    const appearance = (element: Element) => {
      const style = getComputedStyle(element)
      return { border: style.borderLeftColor, background: style.backgroundImage, shadow: style.boxShadow }
    }
    const dnaStyle = await dnaCard.evaluate(appearance)
    const rnaStyle = await rnaCard.evaluate(appearance)
    const wgsStyle = await page.locator('.catalog-service-card[data-family="wgs"]').evaluate(appearance)
    const wtsStyle = await page.locator('.catalog-service-card[data-family="wts"]').evaluate(appearance)
    expect(new Set([dnaStyle.border, rnaStyle.border, wgsStyle.border, wtsStyle.border]).size).toBe(4)
    expect(new Set([dnaStyle.background, rnaStyle.background, wgsStyle.background, wtsStyle.background]).size).toBe(4)
    expect(dnaStyle.border).not.toBe(rnaStyle.border)
    expect(dnaStyle.background).not.toBe(rnaStyle.background)
    expect(dnaStyle.shadow).not.toBe(rnaStyle.shadow)
    await expect(dnaCard.locator('.badge-dna')).toHaveText("DNA")
    await expect(rnaCard.locator('.badge-rna')).toHaveText("RNA")
    await expect(dnaCard.locator('.badge-panel-dna')).toHaveText("Targeted DNA panel")
    await expect(rnaCard.locator('.badge-panel-rna')).toHaveText("Targeted RNA panel")
    for (const badge of [dnaCard.locator('.badge-dna'), dnaCard.locator('.badge-panel-dna'), dnaCard.locator('.catalog-value-badge').first()]) {
      const shadow = await badge.evaluate(element => getComputedStyle(element).boxShadow)
      expect(shadow).toContain("inset")
      expect(shadow.split(")").length).toBeGreaterThan(3)
    }
    const badgeSurface = (element: Element) => getComputedStyle(element).backgroundColor
    expect(await dnaCard.locator('.badge-dna').evaluate(badgeSurface))
      .not.toBe(await rnaCard.locator('.badge-rna').evaluate(badgeSurface))
    expect(await dnaCard.locator('.badge-panel-dna').evaluate(badgeSurface))
      .not.toBe(await rnaCard.locator('.badge-panel-rna').evaluate(badgeSurface))
    await page.screenshot({ path: `test-results/catalog-modality-colors-${theme}.png`, fullPage: true })
    // Keep enough overflow to exercise scrolling even with one compact desktop row.
    await page.setViewportSize({ width: theme === "light" ? 1440 : 390, height: 600 })
    const scrollArea = page.getByRole("main")
    await scrollArea.hover()
    await page.mouse.wheel(0, 500)
    await expect.poll(() => scrollArea.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
    await page.getByRole("button", { name: "Back to top", exact: true }).click()
    await expect.poll(() => scrollArea.evaluate(element => element.scrollTop)).toBe(0)
    await page.setViewportSize({ width: theme === "light" ? 1440 : 390, height: 900 })
    await page.getByLabel("Biological group").selectOption("solid")
    await page.getByLabel("Diagnosis", { exact: true }).selectOption("breast")
    await page.getByLabel("Molecular modality").selectOption("dna")
    await expect(page.getByRole("article")).toHaveCount(2)
    await expect(page.locator('.catalog-service-card[data-modality="dna"]')).toHaveCount(2)
    expect(await page.getByRole("article").first().evaluate(element => getComputedStyle(element).borderTopWidth)).toBe("4px")
    await page.screenshot({ path: `test-results/catalog-discovery-${theme}.png`, fullPage: true })
    await page.getByLabel("Compare Breast panel").check()
    await page.getByLabel("Compare Breast WGS").check()
    await expect(page.getByRole("table")).toContainText("Estimated")
    const comparison = page.getByRole("table", { name: "Published service comparison" })
    await expect(comparison.getByRole("rowheader", { name: "Method", exact: true })).toBeVisible()
    await expect(comparison.locator(".badge-panel-dna")).toHaveCount(1)
    await expect(comparison.locator(".badge-wgs")).toHaveCount(1)
    await comparison.scrollIntoViewIfNeeded()
    await page.screenshot({ path: `test-results/catalog-comparison-${theme}.png`, fullPage: true })
    await page.getByRole("button", { name: "By Assay" }).click()
    await expect(page.getByRole("article")).toHaveCount(2)
    await page.getByLabel("Assay", { exact: true }).selectOption("solid_GMSv3")
    await expect(page.getByRole("article")).toHaveCount(1)
    await page.getByLabel("Assay", { exact: true }).selectOption("")
    await page.getByLabel("Search diagnoses, genes and assays").fill("BRCA1")
    await expect(page.getByRole("article")).toHaveCount(1)
    await expect(page.getByText("Matched: Published gene scope")).toBeVisible()
    await page.getByRole("button", { name: "View details" }).click()
    await expect(page.getByRole("cell", { name: "BRCA1", exact: true })).toBeVisible()
    await expect(page.getByText(/1 list genes outside validated assay coverage/)).toBeVisible()
    await expect(page.getByRole("cell", { name: "BRCA1 DNA repair associated", exact: true })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: /Transcript/ })).toBeVisible()
    await expect(page.getByRole("cell").filter({ hasText: "NM_007294.4" })).toContainText("RS MC+")
    await expect(page.getByText("ENST00000357654.9", { exact: true })).toHaveCount(0)
    await expect(page.getByRole("tab", { name: /SNV/ })).toHaveAttribute("aria-selected", "true")
    await page.screenshot({ path: `test-results/catalog-details-snv-${theme}.png`, fullPage: true })
    await page.getByRole("tab", { name: /CNV/ }).click()
    await expect(page.getByRole("tabpanel").getByRole("link", { name: "MYC", exact: true })).toBeVisible()
    await expect(page.getByRole("tabpanel").getByRole("link", { name: "BRCA1", exact: true })).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  })
}
