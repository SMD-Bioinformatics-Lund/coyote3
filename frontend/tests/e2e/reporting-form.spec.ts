import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const [theme, width] of [["light", 1440], ["dark", 390]] as const) {
  test(`retained reporting values and tier visibility in ${theme} at ${width}px`, async ({ page }, testInfo) => {
    await installApiFixtures(page, path => {
      if (path.endsWith("/auth/whoami")) return { json: { username: "synthetic", roles: ["superuser"], permissions: [], ui_settings: { theme } } }
      if (path === "/api/v1/resources/aspc/example/context") return { json: {
        assay_config: { aspc_id: "example", asp_category: "dna", analysis_types: ["SNV"], reporting: {
          report_sections: ["CNV"], reportable_tiers: { SNV: [1], CNV: [2], TRANSLOCATION: [3] },
        } }, form: { fields: {
          analysis_types: { data_type: "list", display_type: "checkbox-group", options: ["SNV", "CNV"] },
          reporting: { label: "Reporting", display_type: "reporting-structured", groups: [
            { title: "Report sections", fields: [{ key: "report_sections", label: "Report sections", type: "checkbox-group", options: ["SNV", "CNV"], options_from_field: "analysis_types", show_unavailable_options: true }] },
            { title: "Reportable tiers", fields: ["SNV", "CNV", "TRANSLOCATION"].map(analysis => ({ key: `reportable_tiers.${analysis}`, label: `${analysis} tiers`, type: "checkbox-group", options: ["1", "2", "3", "4"] })) },
          ] },
        }, sections: { Reporting: ["reporting"] } },
      } }
    })
    await page.setViewportSize({ width, height: 1000 })
    await page.goto("/admin/aspc/example/view")
    await expect(page.getByRole("checkbox", { name: "CNV", exact: true })).toBeChecked()
    await expect(page.getByRole("checkbox", { name: "CNV", exact: true })).toBeDisabled()
    await expect(page.getByText("CNV tiers", { exact: true })).toBeVisible()
    await expect(page.getByText("SNV tiers", { exact: true })).toHaveCount(0)
    await expect(page.getByText("TRANSLOCATION tiers", { exact: true })).toHaveCount(0)
    await expect(page.getByRole("checkbox", { name: "2", exact: true })).toBeChecked()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    await page.screenshot({ path: testInfo.outputPath(`reporting-${theme}.png`), fullPage: true })
  })
}
