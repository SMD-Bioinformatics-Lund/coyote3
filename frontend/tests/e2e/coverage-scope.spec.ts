import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  for (const width of [390, 1280]) {
    test(`coverage scope selection in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      let selected: string | null = null
      await installApiFixtures(page, (path, url) => {
        if (path.endsWith("/auth/whoami")) return { json: {
          username: "synthetic", role: "user", roles: [], access_level: 1,
          permissions: ["sample:view"], ui_settings: { theme },
        } }
        if (path.endsWith("/edit-context")) return { json: {
          sample: {
            name: "SYNTHETIC", asp_category: "dna", environment: "testing",
            analysis_intents: ["somatic"], files: { cov: "/synthetic/coverage.json" },
            data_counts: { cov: true },
          }, analysis_sections: ["COVERAGE"],
        } }
        if (path.endsWith("/coverage")) {
          selected = url.searchParams.get("gene_list_id")
          return { json: {
            coverage: { genes: {} }, cov_table: {}, gene_scope: [], cov_cutoff: 500,
            smp_grp: "synthetic", gene_list_id: selected,
            gene_lists: [{ id: "focused", label: "Focused genes" }],
          } }
        }
      })
      await page.goto("/samples/SYNTHETIC?tab=coverage")
      const select = page.getByRole("combobox", { name: "Coverage gene list" })
      await expect(select).toHaveText("Assay scope")
      await expect(page.locator("html")).toHaveClass(new RegExp(theme))
      await select.focus()
      await page.keyboard.press("Enter")
      await page.getByRole("option", { name: "Focused genes" }).click()
      await expect.poll(() => selected).toBe("focused")
      await expect(select).toHaveText("Focused genes")
      const bounds = await select.boundingBox()
      expect(bounds).not.toBeNull()
      expect(bounds!.x).toBeGreaterThanOrEqual(0)
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width)
      await page.screenshot({ path: testInfo.outputPath("coverage-scope.png"), fullPage: true })
      await select.click()
      await page.getByRole("option", { name: "Assay scope" }).click()
      await expect(select).toHaveText("Assay scope")
    })
  }
}
