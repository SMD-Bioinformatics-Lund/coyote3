import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  for (const width of [390, 1280, 1920]) {
    test(`${theme} sample composition stays proportional at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1080 })
      await installApiFixtures(page, (path) => {
        if (path === "/api/v1/auth/whoami") return { json: {
          username: "demo", role: "superuser", roles: ["superuser"], access_level: 100000,
          permissions: [], ui_settings: { theme },
        } }
        if (path.startsWith("/api/v1/dashboard/metrics/")) return { json: {
          total_samples: 3,
          capacity_counts: { users_total: 2, roles_total: 32, asps_total: 11, aspcs_total: 39, isgl_total: 8 },
          user_samples_stats: {
            "demo-dna": { total: 2, analysed: 1, pending: 1 },
            "demo-rna": { total: 1, analysed: 0, pending: 1 },
          },
          sample_stats: {
            ingest_statuses: { ready: 3 }, omics_layers: { dna: 1, rna: 2 },
            sequencing_scopes: { panel: 3 }, pair_count: { paired: 1, unpaired: 2 },
          },
          user_scope_summary: { total_samples: 3, sample_stats: {
            profiles: { testing: 3 },
            pipelines: [{ name: "SyntheticFixture", version: "1.0", count: 3, analysed: 1 }],
          } },
        } }
      })
      await page.goto("/")
      const snapshot = page.locator(".dashboard-snapshot-card")
      await expect(snapshot).toHaveCount(3)
      const snapshotStyles = await snapshot.evaluateAll(cards => cards.map(card => {
        const style = getComputedStyle(card)
        return {
          border: style.borderTopColor, width: style.borderTopWidth, borderStyle: style.borderTopStyle,
          radius: style.borderTopLeftRadius, background: style.backgroundImage,
          shadow: style.boxShadow, padding: style.padding,
        }
      }))
      expect(snapshotStyles[0].width).toBe("1px")
      expect(snapshotStyles[0].borderStyle).toBe("solid")
      expect(snapshotStyles[0].border).not.toBe("rgba(0, 0, 0, 0)")
      for (const style of snapshotStyles) expect(style).toEqual(snapshotStyles[0])
      await snapshot.first().locator("..").screenshot({ path: testInfo.outputPath(`${theme}-snapshot-${width}.png`) })
      await page.locator(".surface-panel").filter({ hasText: "Resource Capacity" }).screenshot({ path: testInfo.outputPath(`${theme}-capacity-${width}.png`) })
      const panel = page.locator(".surface-panel").filter({ hasText: "Sample Composition" })
      await expect(panel.getByRole("img", { name: /Omics: dna 1 of 3, rna 2 of 3/ })).toBeVisible()
      await expect(panel.getByText("1 analysed · 2 awaiting review")).toBeVisible()
      await expect(panel.getByText("33% complete")).toBeVisible()
      const donutSector = panel.locator(".recharts-pie-sector .recharts-sector").first()
      await expect(donutSector).toBeVisible()
      expect(await donutSector.evaluate(element => getComputedStyle(element).filter)).toContain("drop-shadow")
      const layout = await panel.evaluate((element) => ({
        width: element.clientWidth,
        scrollWidth: element.scrollWidth,
        figures: [...element.querySelectorAll("figure")].map((figure) => ({
          width: figure.clientWidth, scrollWidth: figure.scrollWidth,
          height: figure.getBoundingClientRect().height,
        })),
        bars: [...element.querySelectorAll('[aria-hidden="true"].h-2\\.5')]
          .map((bar) => bar.getBoundingClientRect().height),
      }))
      expect(layout.scrollWidth).toBeLessThanOrEqual(layout.width + 1)
      expect(layout.figures).toHaveLength(5)
      for (const figure of layout.figures) {
        expect(figure.scrollWidth).toBeLessThanOrEqual(figure.width + 1)
        expect(figure.height).toBeLessThan(200)
      }
      expect(layout.bars).toHaveLength(1)
      expect(layout.bars[0]).toBeLessThanOrEqual(12)
      await panel.screenshot({ path: testInfo.outputPath(`${theme}-composition-${width}.png`) })
      const workload = page.locator(".surface-panel").filter({ hasText: "Review Workload" })
      await expect(workload.getByRole("progressbar", { name: "demo-rna review progress" })).toHaveAttribute("aria-valuenow", "0")
      await expect(workload.getByRole("progressbar", { name: "demo-dna review progress" })).toHaveAttribute("aria-valuenow", "50")
      await workload.screenshot({ path: testInfo.outputPath(`${theme}-workload-${width}.png`) })
    })
  }
}
