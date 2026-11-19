import { expect, test } from "@playwright/test"
import { createHash } from "node:crypto"
import { installApiFixtures } from "./support/api-fixtures"
import type { VepReference } from "../../src/pages/static/VepReferencePage"

// Synthetic reference data keeps browser behavior independent of Atlas source files.
const diagram = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300"><rect width="1200" height="300" fill="#eee"/><path d="M40 150h1120" stroke="#555" stroke-width="8"/></svg>'
const references: VepReference[] = ["116", "103"].map(release => ({
  vep_id: release,
  source: "https://example.test/cache",
  vc_translation_source: "https://example.test/classes",
  conseq_translation_source: "https://example.test/consequences",
  conseq_translations: {
    missense_variant: { display: "missense_variant", desc: "A sequence variant that changes an amino acid.", group: "missense", impact: "MODERATE", so_term: "SO:0001583" },
  },
  consequence_groups: { missense: ["missense_variant"] },
  variant_class_translations: { SNV: { short: "SNV", desc: "Single nucleotide variant", displayname: "SNV", so_term: "SO:0001483" } },
  db_info: { GRCh38: { published_sources: { Ensembl: release } } },
  consequence_diagram: { mime_type: "image/svg+xml", sha256: createHash("sha256").update(diagram).digest("hex"), width: 1200, height: 300, source_url: "https://example.test/diagram.svg", release },
}))

for (const width of [1440, 390]) {
  test(`VEP references and diagrams fit ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    await installApiFixtures(page, path => {
      if (path === "/api/v1/auth/whoami") return { status: 401, json: { detail: "Not authenticated" } }
      if (path === "/api/v1/public/vep") return { json: { versions: references.map(row => row.vep_id).sort((a, b) => Number(b) - Number(a)) } }
      if (path.startsWith("/api/v1/public/vep/")) {
        const reference = references.find(row => row.vep_id === path.split("/").pop())
        return reference ? { json: reference } : { status: 404, json: { detail: "Not installed" } }
      }
    })
    await page.route("**/api/v1/public/vep/*/diagram", async route => {
      const release = new URL(route.request().url()).pathname.split("/").at(-2)
      const metadata = references.find(row => row.vep_id === release)?.consequence_diagram
      if (!metadata) return route.fulfill({ status: 404 })
      await route.fulfill({ contentType: metadata.mime_type, body: diagram })
    })
    await page.goto("/about/vep")
    await expect(page.getByRole("heading", { name: "VEP Reference", exact: true })).toBeVisible()
    const image = page.getByRole("img", { name: /Ensembl 116 variant consequences/ })
    await expect(image).toBeVisible()
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await expect(page.getByLabel("VEP release")).toHaveValue("116")
    await page.screenshot({ path: testInfo.outputPath("vep-reference.png"), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    await page.getByLabel("Search VEP terms").fill("SO:0001583")
    await expect(page.getByRole("link", { name: "SO:0001583", exact: true })).toBeVisible()
    await page.getByText("missense_variant", { exact: true }).focus()
    await expect(page.getByText("Group: missense", { exact: true })).toBeVisible()
    await page.getByLabel("VEP release").selectOption("103")
    await expect(page).toHaveURL(/version=103/)
    const oldImage = page.getByRole("img", { name: /Ensembl 103 variant consequences/ })
    await expect.poll(() => oldImage.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await page.getByLabel("Search VEP terms").fill("")
    await page.getByRole("tab", { name: "Variant classes", exact: true }).click()
    await expect(page.getByRole("columnheader", { name: "Variant class", exact: true })).toBeVisible()
    await page.getByRole("tab", { name: "Cache sources", exact: true }).click()
    await expect(page.getByRole("heading", { name: "GRCh38", exact: true })).toBeVisible()
  })
}
