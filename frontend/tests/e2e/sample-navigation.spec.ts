import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const scope of ["production", "all"]) {
  test(`assay navigation filters the worklist and resets pagination in ${scope} scope`, async ({ page }) => {
    const requests: URL[] = []
    await installApiFixtures(page, (path, url) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "synthetic-admin", roles: ["superuser"], access_level: 100000,
        permissions: [], ui_settings: { sample_list_layout: "classic", sample_list_modern_view_tried: true },
      } }
      if (path === "/api/v1/samples/navigation-counts") return { json: {
        counts: { "dna:panel:hematology": 1, "dna:wgs:hematology": 1 }, profile_scope: scope,
      } }
      if (path === "/api/v1/samples") {
        requests.push(url)
        const family = url.searchParams.get("panel_tech")
        const selected = url.searchParams.get("panel_type") === "dna"
          && url.searchParams.get("assay_group") === "hematology"
          && (family === "panel" || family === "wgs")
          && url.searchParams.get("live_page") === "1"
        const rows = selected ? [{
          _id: `synthetic-${family}`, name: `SYNTHETIC_${family.toUpperCase()}`,
          asp_id: `synthetic-${family}`, asp_category: "dna", environment: "production",
          ingest_status: "ready", data_counts: {},
        }] : []
        return { json: { live_samples: rows, done_samples: [], live_total: rows.length, done_total: 0 } }
      }
    })
    await page.goto(`/samples?profile_scope=${scope}&live_page=7&reported_page=3`)
    await expect(page.getByRole("heading", { name: "Samples", exact: true })).toBeVisible()

    for (const family of ["panel", "wgs"]) {
      await page.getByRole("button", { name: /^dna$/i }).click()
      await page.getByRole("heading", { name: family, exact: true }).locator("..")
        .getByRole("button", { name: /^hematology / }).click()
      await expect(page.getByRole("link", { name: `SYNTHETIC_${family.toUpperCase()}`, exact: true })).toBeVisible()
      const location = new URL(page.url())
      expect(location.searchParams.has("live_page")).toBe(false)
      expect(location.searchParams.has("reported_page")).toBe(false)
      expect(requests.at(-1)?.searchParams.get("profile_scope")).toBe(scope)
      expect(requests.at(-1)?.searchParams.get("panel_tech")).toBe(family)
    }
  })
}
