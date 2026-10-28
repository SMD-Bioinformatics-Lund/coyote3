import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const theme of ["light", "dark"]) {
  test(`annotation deactivation and historical search in ${theme} mode`, async ({ page }, testInfo) => {
    let inactive = false
    const writes: unknown[] = []
    await installApiFixtures(page, (path, _url, route) => {
      if (path.endsWith("/auth/whoami")) return { json: {
        username: "synthetic.reviewer", roles: ["superuser"], permissions: [], ui_settings: { theme },
      } }
      if (path.endsWith("/small-variants/finding-1")) return { json: {
        sample: { _id: "sample-1", name: "SYNTHETIC", asp_id: "demo-panel", environment: "testing" },
        variant: { _id: "finding-1", SAMPLE_ID: "sample-1", CHROM: "17", POS: 1, REF: "A", ALT: ["G"], GT: [],
          INFO: { selected_CSQ: { SYMBOL: "TP53", Feature: "NM_1", HGVSp: "p.Arg1Gly" } } },
        latest_classification: { class: 2, is_active: !inactive, historical_sample_match: inactive,
          author: "current.reviewer", time_created: "2026-03-01T10:00:00Z",
          history: [
            { _id: "prior", class: 1, text: "Previous matching interpretation.", author: "previous.reviewer", time_created: "2026-02-01T10:00:00Z", is_active: false },
            { _id: "oldest", class: 3, text: "Original matching interpretation.", author: "first.reviewer", time_created: "2026-01-01T10:00:00Z" },
          ],
        },
        annotations: [], other_classifications: [],
      } }
      if (path.endsWith("/classifications/tier")) {
        writes.push(route.request().postDataJSON())
        inactive = true
        return { json: { status: "ok" } }
      }
      if (path.endsWith("/common/search/tiered_variants")) return { json: {
        docs: [
          { _id: "original", variant: "p.Arg1Gly", gene: "TP53", class: 2, nomenclature: "p", is_active: false,
            samples: { "sample-1": { sample_id: "sample-1", name: "SYNTHETIC", sample_name: "SYNTHETIC" } } },
          { _id: "legacy", variant: "p.Arg2Gly", gene: "TP53", class: 1, nomenclature: "p", is_active: false,
            legacy_fallback: true, samples: {} },
        ], assay_choices: [], tier_stats: { total: {}, by_assay: {} },
      } }
    })
    await page.goto("/samples/SYNTHETIC/variant/finding-1")
    await expect(page.getByRole("button", { name: "Tier 2", exact: true })).toHaveAttribute("aria-pressed", "true")
    await expect(page.getByRole("region", { name: "Classification history" })).toContainText("previous.reviewer")
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      await page.getByRole("region", { name: "Classification history" }).scrollIntoViewIfNeeded()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`classification-card-${width}.png`) })
    }
    const deactivate = page.getByRole("button", { name: "Deactivate", exact: true })
    await expect(deactivate).toBeVisible()
    await deactivate.focus()
    await page.keyboard.press("Enter")
    await expect(page.getByRole("alertdialog")).toContainText("history are retained")
    await page.getByRole("button", { name: "Deactivate annotations", exact: true }).click()
    await expect(page.getByText("Inactive", { exact: true }).first()).toBeVisible()
    await expect(page.getByText(/Historical annotation linked to this sample/)).toBeVisible()
    expect(writes).toEqual([{ resource_type: "small_variant", resource_ids: ["finding-1"], tier: 2, apply: false }])
    await page.getByRole("button", { name: "Deactivate group annotations", exact: true }).click()
    await expect(page.getByRole("alertdialog")).toContainText("every assay and diagnosis")
    await page.getByRole("button", { name: "Deactivate annotations", exact: true }).click()
    await expect.poll(() => writes.length).toBe(2)
    expect(writes[1]).toEqual({ resource_type: "small_variant", resource_ids: ["finding-1"], tier: 2,
      apply: false, deactivation_scope: "group" })

    await page.goto("/variants/search?search_str=TP53&search_mode=gene")
    await expect(page.getByRole("note")).toContainText("even if inactive")
    await expect(page.getByRole("link", { name: "SYNTHETIC", exact: true })).toBeVisible()
    await expect(page.getByText("Inactive", { exact: true })).toHaveCount(2)
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      await expect(page.getByRole("note")).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`annotation-history-${width}.png`), fullPage: true })
    }
  })
}
