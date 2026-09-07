import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`catalog draft and preview fit ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    const catalog = { header: "Assay Catalog", description: "Synthetic catalog.",
      version: 1, layout: { order: ["wgs"] }, modalities: {
        wgs: { label: "Whole Genome Sequencing (WGS)", categories: {
          solid: { label: "Solid", asp_id: "assay", aspc_id: "assay_base",
            input_material: ["DNA"], analysis: ["somatic"], tat: "7-10 days", gene_lists: [] },
        } },
      } }
    let version = { _id: "draft-one", status: "draft", revision: 1, base_version: 1,
      content_version: null, catalog, created_by: "author", content_editors: ["author"],
      review: {}, lifecycle: [] }
    await installApiFixtures(page, (path, url, route) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "author", roles: ["catalog_author"], role: "catalog_author",
        permissions: ["catalog:view", "catalog:draft", "catalog:submit"],
      } }
      if (path === "/api/v1/admin/assay-catalog") return { json: {
        catalog, has_published: true, items: [version],
        sources: { asps: [{ asp_id: "assay", label: "Assay" }],
          aspcs: [{ asp_id: "assay", aspc_id: "assay_base", subpanel_id: "base" }],
          gene_lists: [] },
        presets: { input_material: ["DNA", "RNA", "FFPE"], analysis: ["somatic", "germline"],
          sample_modes: ["Tumor-only", "Tumor-normal"] },
        reviewers: [{ username: "reviewer", name: "Reviewer" }], publishers: [],
      } }
      if (path.endsWith("/assay-catalog/preview")) {
        const document = route.request().postDataJSON().document
        const selected = url.searchParams.get("cat") === "solid"
        return { json: {
          order: document.layout.order, modalities: document.modalities,
          right: selected ? { ...document.modalities.wgs.categories.solid, title: "Solid" }
            : { title: document.header, description: document.description },
          genes: selected ? [{ display_symbol: "TP53", gene_name: "Synthetic gene" }] : [],
          stats: { total: selected ? 1 : 0, covered_total: selected ? 1 : 0, germline_total: 0 },
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
    await expect(preview.getByRole("heading", { name: "Modalities" })).toBeVisible()
    await preview.getByRole("button", { name: "Whole Genome Sequencing (WGS)" }).click()
    await preview.getByRole("button", { name: "Solid", exact: true }).click()
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
    await expect(preview.getByRole("heading", { name: "Modalities" })).toBeVisible()
  })
}
