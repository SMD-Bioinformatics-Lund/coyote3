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
        genes: ["BRCA1"], excluded_gene_count: 1 }],
    }
    const wgs = { ...panel, offering_id: "breast-wgs", title: "Breast WGS", family: "wgs",
      assay_id: "solid_wgs", assay_label: "Solid WGS",
      price: { ...panel.price, amount: "400.00", kind: "estimated" },
      gene_scopes: [{ ...panel.gene_scopes[0], genes: ["TP53"] }],
    }
    await installApiFixtures(page, (path) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "viewer", role: "user", roles: ["user"], permissions: [], ui_settings: { theme },
      } }
      if (path === "/api/v1/public/assay-catalog/offerings") return { json: {
        version: 2, header: "Genomic test catalog", description: "Published services", offerings: [panel, wgs],
      } }
    })
    await page.goto("/public/catalog")
    await expect(page.getByRole("button", { name: "By Diagnosis" })).toHaveAttribute("aria-pressed", "true")
    await page.getByLabel("Biological group").selectOption("solid")
    await page.getByLabel("Diagnosis", { exact: true }).selectOption("breast")
    await expect(page.getByRole("article")).toHaveCount(2)
    await page.getByLabel("Compare Breast panel").check()
    await page.getByLabel("Compare Breast WGS").check()
    await expect(page.getByRole("table")).toContainText("Estimated")
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
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
  })
}
