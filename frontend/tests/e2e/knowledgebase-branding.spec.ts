import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const view of [{ theme: "light", width: 390 }, { theme: "dark", width: 1440 }]) {
  test(`knowledgebase logos replace names with readable fallbacks in ${view.theme}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: view.width, height: 1000 })
    await installApiFixtures(page, path => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "synthetic", roles: ["superuser"], role: "superuser", access_level: 100000,
        ui_settings: { theme: view.theme },
      } }
      if (path === "/api/v1/public/knowledgebases/status") return { json: {
        releases: [
          { source: "cosmic_cancer_gene_census", release: "104", records: 768, status: "active" },
          { source: "civic", release: "2026-09-01", records: 100, status: "active" },
          { source: "iarc_tp53", release: "R21", records: 100, status: "active" },
        ],
      } }
    })
    await page.route("**/logos/civic-vector.svg", route => route.abort())
    await page.goto("/knowledgebases")
    const logos = page.getByRole("img", { name: "COSMIC logo" })
    await expect(logos).toHaveCount(2)
    await expect.poll(() => logos.evaluateAll(images => images.every(image => (image as HTMLImageElement).naturalWidth > 0))).toBe(true)
    await expect(page.getByText("COSMIC", { exact: true })).toHaveCount(0)
    await expect(page.getByText("CIViC", { exact: true })).toHaveCount(2)
    await expect(page.getByText("IARC TP53", { exact: true })).toHaveCount(2)
    await expect(page.getByRole("cell", { name: "cancer gene census", exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath("knowledgebase-branding.png"), fullPage: true })
  })
}
