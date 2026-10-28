import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

test("empty catalog panel fills the viewport without stretching preview cards", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const catalog = { header: "Assay Catalog", description: "Synthetic catalog.",
    version: 1, layout: { order: [] }, modalities: {} }
  await installApiFixtures(page, (path) => {
    if (path === "/api/v1/admin/assay-catalog") return { json: {
      catalog, has_published: false, items: [], sources: {}, presets: {},
      reviewers: [], publishers: [],
    } }
    if (path.endsWith("/assay-catalog/preview/offerings")) return { json: {
      ...catalog, offerings: [],
    } }
  })
  await page.goto("/admin/assay-catalog")
  await expect(page.getByText("No published services", { exact: true })).toBeVisible()
  const preview = page.getByRole("region", { name: "Catalog preview" })
  const panel = preview.locator("../..")
  const main = page.getByRole("main")
  const panelBounds = await panel.boundingBox()
  const mainBounds = await main.boundingBox()
  const previewBounds = await preview.boundingBox()
  expect(panelBounds).not.toBeNull()
  expect(mainBounds).not.toBeNull()
  expect(previewBounds).not.toBeNull()
  expect(Math.abs(panelBounds!.y + panelBounds!.height - mainBounds!.y - mainBounds!.height))
    .toBeLessThanOrEqual(16)
  expect(previewBounds!.height).toBeLessThan(panelBounds!.height / 2)
  await page.evaluate(() => document.documentElement.classList.remove("dark"))
  await page.screenshot({ path: "/tmp/catalog-empty-light.png" })
  await page.evaluate(() => document.documentElement.classList.add("dark"))
  await page.screenshot({ path: "/tmp/catalog-empty-dark.png" })
})

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`catalog draft and preview fit ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    const catalog = { header: "Assay Catalog", description: "Synthetic catalog.",
      version: 1, layout: { order: ["wgs"] }, modalities: {
        wgs: { label: "Whole Genome Sequencing (WGS)", categories: {
          solid: { label: "Solid", asp_id: "assay", aspc_id: "assay_base",
            input_material: ["DNA"], analysis: ["SNV"], tat: "7-10 days", gene_lists: [] },
        } },
      } }
    let version = { _id: "draft-one", status: "draft", revision: 1, base_version: 1,
      content_version: null, catalog, created_by: "author", content_editors: ["author"],
      review: {}, lifecycle: [] }
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "author", roles: ["catalog_author"], role: "catalog_author",
        permissions: ["catalog:view", "catalog:draft", "catalog:submit"],
      } }
      if (path === "/api/v1/admin/assay-catalog") return { json: {
        catalog, has_published: true, items: [version],
        sources: { asps: [{ asp_id: "assay", label: "Assay" }],
          aspcs: [{ asp_id: "assay", aspc_id: "assay_base", diagnosis_id: "base" }],
          gene_lists: [] },
        presets: { input_material: ["DNA", "RNA", "FFPE"], analysis: ["SNV", "CNV"],
          sample_modes: ["Tumor-only", "Tumor-normal"] },
        reviewers: [{ username: "reviewer", name: "Reviewer" }], publishers: [],
      } }
      if (path.endsWith("/assay-catalog/preview/offerings")) {
        const document = route.request().postDataJSON().document
        return { json: { version: 1, header: document.header, description: document.description,
          offerings: [{ offering_id: "solid", title: "Solid", group_id: "solid", group_label: "Solid",
            diagnosis_id: "base", diagnosis_label: "No diagnosis / General testing",
            modality: "dna", family: "wgs", assay_id: "assay", assay_label: "Assay",
            description: "", analysis: ["SNV"], price: null, pricing_message: "Contact for pricing",
            turnaround: "7-10 days", input_material: ["DNA"], report_deliverables: ["PDF"],
            methodology: "Whole genome sequencing", limitations: "Validated scope",
            ordering_information: "", gene_scopes: [{ list_id: "genes", label: "Covered genes",
              revision: 1, analysis: "SNV", genes: ["TP53"], excluded_gene_count: 0 }] }],
        } }
      }
      if (path.endsWith("/assay-catalog/preview/matrix")) {
        const document = route.request().postDataJSON().document
        return { json: {
          modalities: document.modalities, order: document.layout.order,
          columns: [{ mod: "wgs", cat: "solid", assay: "Solid", assay_group: "Solid",
            modality_label: document.modalities.wgs.label, isgl_key: "assay",
            isgl_label: "Covered genes", placeholder: false }],
          genes: ["TP53"], matrix: { TP53: { wgs: { solid: { assay: true } } } },
          gene_markers: { TP53: { oncokb: true, cosmic_cgc: true, civic: true, clinpgx: true } },
          page: 1, per_page: 100, total: 1, has_next: false, has_previous: false,
        } }
      }
      if (path.endsWith("/assay-catalog/drafts") || path.endsWith("/versions/draft-one")) return { json: version }
      if (path.endsWith("/drafts/draft-one")) {
        version = { ...version, revision: version.revision + 1, catalog: route.request().postDataJSON().catalog }
        return { json: version }
      }
    })
    await page.goto("/admin/assay-catalog")
    await expect(page.getByRole("region", { name: "Catalog preview" })).toBeVisible()
    await page.getByRole("button", { name: "Edit published catalog" }).click()
    await expect(page.getByLabel("Catalog heading")).toBeVisible()
    await page.getByRole("button", { name: "Whole Genome Sequencing (WGS)" }).click()
    await page.getByRole("button", { name: "Solid", exact: true }).click()
    await page.getByRole("checkbox", { name: "RNA", exact: true }).check()
    await expect(page.getByLabel("Turnaround value or range")).toHaveValue("7-10")
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: `/tmp/catalog-builder-${viewport.width}.png`, fullPage: true })
    await page.getByRole("button", { name: "Save draft", exact: true }).click()
    await expect(page.getByRole("region", { name: "Catalog preview" })).toBeVisible()
    await expect(page.getByLabel("Catalog heading")).toHaveCount(0)
    const preview = page.getByRole("region", { name: "Catalog preview" })
    await expect(preview.getByRole("navigation", { name: "Test categories" })).toBeVisible()
    await preview.getByRole("button", { name: "View details" }).click()
    await expect(preview.getByText("TP53", { exact: true })).toBeVisible()
    await expect(preview.getByText("7-10 days", { exact: true })).toBeVisible()
    expect(await preview.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)")
    await page.screenshot({ path: `/tmp/catalog-preview-${viewport.width}.png`, fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await preview.getByRole("button", { name: "Matrix", exact: true }).click()
    await expect(preview.getByRole("heading", { name: "Assay Catalog Matrix" })).toBeVisible()
    await expect(preview.getByText("TP53", { exact: true })).toBeVisible()
    await expect(page).toHaveURL(/admin\/assay-catalog\?version=draft-one/)
    await expect(preview.getByRole("checkbox", { name: "Annotations" })).not.toBeChecked()
    await preview.getByRole("checkbox", { name: "Annotations" }).check()
    await expect(preview.getByRole("columnheader", { name: "Annotations" })).toBeVisible()
    const tags = preview.getByLabel("Knowledgebase sources")
    await expect(tags).toBeVisible()
    expect(await tags.locator("span").first().evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeLessThanOrEqual(8)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: `/tmp/catalog-matrix-${viewport.width}.png`, fullPage: true })
    await preview.getByRole("button", { name: "Catalog", exact: true }).click()
    await preview.getByRole("button", { name: "Back to available tests" }).click()
    await expect(preview.getByRole("navigation", { name: "Test categories" })).toBeVisible()
  })
}
