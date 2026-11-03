import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"] as const) {
  for (const width of [390, 1440]) {
    test(`finding summaries: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      const sample = { name: "SYNTHETIC_CASE" }
      await installApiFixtures(page, path => {
        if (path.endsWith("/auth/whoami")) return { json: {
          username: "synthetic-reviewer", roles: ["superuser"], permissions: [], ui_settings: { theme },
        } }
        if (path.endsWith("/small-variants/synthetic-variant")) return { json: {
          sample, annotations: [], other_classifications: [], transcripts: [],
          variant: {
            _id: "synthetic-variant", CHROM: "1", POS: 10001, REF: "A", ALT: "G",
            variant_class: "SNV", FILTER: ["PASS"],
            INFO: { selected_CSQ: { SYMBOL: "TP53", Feature: "SYNTHETIC_TRANSCRIPT", Consequence: ["missense_variant"], HGVSc: "c.10A>G", HGVSp: "p.Lys4Glu" } },
            GT: [
              { type: "case", GT: "0/1", AF: 0.4, VD: 80, DP: 200 },
              { type: "control", GT: "0/0", AF: 0, VD: 0, DP: 200 },
            ],
          },
        } }
        if (path.endsWith("/translocations/synthetic-translocation")) return { json: {
          sample, annotations: [], other_classifications: [], transcript_combinations: [],
          translocation: {
            _id: "synthetic-translocation", CHROM: "1", POS: 10001, ALT: "N[2:20001[",
            INFO: { SVTYPE: "BND", ANN: [] },
            GT: [{ type: "case", PR: [100, 20], SR: [50, 15] }],
          },
        } }
        if (path.endsWith("/fusions/synthetic-fusion")) return { json: {
          sample, annotations: [], other_classifications: [],
          fusion: {
            _id: "synthetic-fusion", gene1: "BCR", gene2: "ABL1", callers: ["ARRIBA"],
            calls: [{ selected: true, caller: "ARRIBA", breakpoint1: "22:100", breakpoint2: "9:200", spanpairs: 12, spanreads: 7, longestanchor: 0 }],
          },
        } }
      })

      await page.goto("/samples/SYNTHETIC_CASE/variant/synthetic-variant")
      await expect(page.locator("html")).toHaveClass(new RegExp(theme))
      const variant = page.locator(".detail-identity-card")
      await expect(variant.getByText("40.0% (80 / 200)")).toBeVisible()
      await expect(variant.getByText("0.0% (0 / 200)")).toBeVisible()
      const genotype = page.locator("section").filter({ has: page.getByRole("heading", { name: "Sample Genotype", exact: true }) }).last()
      await expect(genotype.getByText("0/1", { exact: true })).toBeVisible()
      await expect(genotype.getByText("0/0", { exact: true })).toBeVisible()
      await expect(genotype.getByText("VAF", { exact: true })).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await variant.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`variant-summary-${theme}-${width}.png`), fullPage: true })

      await page.goto("/samples/SYNTHETIC_CASE/translocation/synthetic-translocation")
      const translocation = page.locator(".detail-identity-card")
      await expect(translocation.getByText("100/20")).toBeVisible()
      await expect(translocation.getByText("50/15")).toBeVisible()
      await expect(page.getByRole("heading", { name: "Sample Read Evidence", exact: true })).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await translocation.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`translocation-summary-${theme}-${width}.png`), fullPage: true })

      await page.goto("/samples/SYNTHETIC_CASE/fusion/synthetic-fusion")
      await expect(page.locator(".detail-hero .type-card-title")).toHaveText("BCR::ABL1")
      const fusion = page.locator(".detail-identity-card")
      await expect(fusion.getByText("Spanning pairs", { exact: true })).toBeVisible()
      await expect(fusion.getByText("12", { exact: true })).toBeVisible()
      await expect(fusion.getByText("7", { exact: true })).toBeVisible()
      await expect(fusion.getByText("0", { exact: true })).toBeVisible()
      await expect(page.getByRole("heading", { name: "Read Support", exact: true })).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      await fusion.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`fusion-summary-${theme}-${width}.png`), fullPage: true })
    })
  }
}
