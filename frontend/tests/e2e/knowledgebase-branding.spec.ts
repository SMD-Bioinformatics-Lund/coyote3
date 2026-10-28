import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const view of [{ theme: "light", width: 390 }, { theme: "dark", width: 1440 }]) {
  test(`COSMIC tiers have source-specific meaning in ${view.theme}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: view.width, height: 1000 })
    await installApiFixtures(page, path => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "synthetic", roles: ["superuser"], ui_settings: { theme: view.theme },
      } }
      if (path.endsWith("/fusions/F1")) return { json: {
        sample: { _id: "sample-1", name: "SYNTHETIC", environment: "testing" },
        fusion: { _id: "F1", gene1: "BCR", gene2: "ABL1", calls: [
          { selected: true, caller: "ARRIBA", breakpoint1: "22:100", breakpoint2: "9:200" },
        ] },
        annotations: [], latest_classification: { class: 1 },
        cosmic: { kind: "fusion", gene_census: [
          { gene_symbol: "ABL1", tier: 1 }, { gene_symbol: "BCR", tier: 2 },
        ] },
      } }
    })
    await page.goto("/samples/SYNTHETIC/fusion/F1")
    const badge = page.getByRole("link", { name: "CGC Tier 1" })
    await badge.scrollIntoViewIfNeeded()
    await badge.focus()
    await expect(page.getByRole("tooltip")).toContainText("not the Coyote clinical classification")
    await expect(page.getByRole("columnheader", { name: "CGC tier" })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath("cosmic-tier.png") })
    await page.keyboard.press("Escape")
    await expect(page.getByRole("tooltip")).toHaveCount(0)
  })
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
