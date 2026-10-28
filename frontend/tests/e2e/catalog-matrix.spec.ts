import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  test(`matrix keeps header and coverage columns aligned in ${theme} mode`, async ({ page }, testInfo) => {
    const dna = ["A", "B", "A", "B"].map((assay, index) => ({
      mod: "dna", modality_label: "DNA", analysis: "SNV", assay_id: assay,
      assay: `Synthetic DNA ${assay}`, assay_group: "Hematology", diagnosis: `Diagnosis ${index}`,
      cat: `panel::hematology::${assay}::diagnosis-${index}`, isgl_key: "genes", isgl_label: "Synthetic genes",
    }))
    const rna = ["Training", "Fusion panel", "WTS hematology", "WTS solid"].map((assay, index) => ({
      mod: "rna", modality_label: "RNA", analysis: "FUSION", assay_id: `rna-${index}`,
      assay: `Synthetic RNA ${assay}`, assay_group: index === 3 ? "Solid tumors" : "Hematology",
      diagnosis: `Diagnosis ${index}`, cat: `rna::group::${index}::base`, isgl_key: "genes", isgl_label: "Synthetic genes",
    }))
    const columns = [...dna, ...rna]
    const matrix = Object.fromEntries(["ABL1", "TP53"].map(gene => [gene, {
      dna: Object.fromEntries(dna.map(col => [col.cat, { genes: true }])),
      rna: Object.fromEntries(rna.map(col => [col.cat, { genes: true }])),
    }]))
    const keyWarnings: string[] = []
    await page.addInitScript(() => localStorage.setItem("coyote3:matrix:annotations", "false"))
    page.on("console", message => {
      if (message.type() === "error" && message.text().includes("same key")) keyWarnings.push(message.text())
    })
    await installApiFixtures(page, (path, url) => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "viewer", roles: ["user"], permissions: [], ui_settings: { theme },
      } }
      if (path.endsWith("/assay-catalog-matrix/context")) {
        const genes = url.searchParams.get("gene") ? [url.searchParams.get("gene")] : ["ABL1", "TP53"]
        return { json: { columns, genes, matrix, gene_markers: {
          TP53: { oncokb: true, cosmic_cgc: true, civic: true, clinpgx: true },
        }, page: 1, per_page: 50,
          total: genes.length, has_next: false, has_previous: false } }
      }
    })
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await page.goto("/public/matrix")
      const table = page.locator(".catalog-matrix")
      for (const analysis of ["SNV", "FUSION", "SNV", "FUSION"]) {
        await page.getByLabel("Gene list type").selectOption(analysis)
        const expected = analysis === "SNV" ? dna : rna
        await expect(table.getByRole("row", { name: "Assays" }).getByRole("columnheader"))
          .toHaveText(expected.map(col => col.assay))
        await expect(table.locator("tbody tr").first().locator("td")).toHaveCount(4)
        const positions = await table.evaluate(el => {
          const headers = el.querySelectorAll('tr[aria-label="Diagnoses / subpanels"] th')
          const cells = el.querySelectorAll("tbody tr:first-child td")
          return [...headers].map((header, i) => Math.abs(header.getBoundingClientRect().left - cells[i].getBoundingClientRect().left))
        })
        expect(positions.every(delta => delta < 1)).toBe(true)
      }
      await expect(table.locator(".matrix-head-mod")).toHaveAttribute("data-tone", "warm")
      await page.getByLabel("Section").selectOption("Hematology")
      await expect(table.getByRole("row", { name: "Assays" }).getByRole("columnheader")).toHaveCount(3)
      await page.getByLabel("Section").selectOption("")
      await page.getByRole("checkbox", { name: "Annotations" }).check()
      await expect(table.locator("tbody tr").first().locator("td")).toHaveCount(5)
      const annotatedGene = table.locator("tbody tr").filter({ has: page.getByRole("link", { name: "TP53", exact: true }) })
      for (const badge of ["OncoKB", "CGC", "CIViC", "PGx"]) {
        await expect(annotatedGene.getByText(badge, { exact: true })).toBeVisible()
      }
      await expect(table.locator("tbody tr").first().getByLabel("Knowledgebase sources")).toHaveCount(0)
      await page.getByRole("checkbox", { name: "Annotations" }).uncheck()
      await expect(annotatedGene.getByLabel("Knowledgebase sources")).toHaveCount(0)
      await page.getByRole("checkbox", { name: "Annotations" }).check()
      await page.getByLabel("Gene search").fill("TP53")
      await page.getByRole("button", { name: "Search", exact: true }).click()
      await expect(table.locator("tbody tr")).toHaveCount(1)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`matrix-${width}.png`), fullPage: true })
    }
    expect(keyWarnings).toEqual([])
  })
}
