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

for (const theme of ["light", "dark"]) {
for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`catalog draft and preview fit ${theme} ${viewport.width}px`, async ({ page }) => {
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
    let invalidPreviewRequests = 0
    let rejectPreview = false
    await installApiFixtures(page, (path, _url, route) => {
      if (path === "/api/v1/auth/whoami") return { json: {
        username: "author", roles: ["catalog_author"], role: "catalog_author",
        permissions: ["catalog:view", "catalog:draft", "catalog:submit"],
        ui_settings: { theme },
      } }
      if (path === "/api/v1/admin/assay-catalog") return { json: {
        catalog, has_published: true, items: [version],
        sources: { asps: [{ asp_id: "assay", label: "Assay", category: "dna", family: "wgs", group: "solid", group_label: "Solid" }],
          aspcs: [{ asp_id: "assay", aspc_id: "assay_base", diagnosis_id: "base" }],
          gene_lists: [{ isgl_id: "synthetic-genes", label: "Synthetic genes", asp_ids: ["assay"],
            asp_groups: ["solid"], diagnosis: [], list_type: ["snv"] }] },
        presets: { input_material: ["DNA", "RNA", "FFPE"], analysis: ["SNV", "CNV"],
          sample_modes: ["Tumor-only", "Tumor-normal"] },
        reviewers: [{ username: "reviewer", name: "Reviewer" }], publishers: [],
      } }
      if (path.endsWith("/assay-catalog/preview/offerings")) {
        const document = route.request().postDataJSON().document
        const sections = Object.values(document.modalities) as { label?: string;
          categories: Record<string, { price?: { amount: string; currency: string } }> }[]
        if (sections.some(section => !section.label || !Object.keys(section.categories).length
          || Object.values(section.categories).some(entry => entry.price
            && (!entry.price.amount || !/^[A-Z]{3}$/.test(entry.price.currency))))) {
          invalidPreviewRequests += 1
          return { status: 422, json: { detail: "Incomplete section or price" } }
        }
        if (rejectPreview) return { status: 422, json: { detail: "Choose an active production configuration" } }
        const entries = document.modalities.wgs.categories
        const parent = entries[entries.solid.parent_key] || {}
        return { json: { version: 1, header: document.header, description: document.description,
          navigation: [
            { node_id: "section:wgs", parent_id: null, label: "Whole Genome Sequencing (WGS)", title: "Whole Genome Sequencing (WGS)", description: "", offering_id: null },
            ...Object.entries(entries).map(([key, raw]) => {
              const value = raw as { label?: string; title?: string; description?: string; parent_key?: string;
                tat?: string; price?: unknown; pricing_message?: string }
              return { node_id: `entry:wgs:${key}`, parent_id: value.parent_key ? `entry:wgs:${value.parent_key}` : "section:wgs",
                label: value.label || key, title: value.title || value.label || key, description: value.description || "",
                turnaround: value.tat || "", price: value.price || null, pricing_message: value.pricing_message || "",
                offering_id: key === "solid" ? "solid" : null }
            }),
          ].map(node => ({ subheading: "", input_material: [], sample_modes: [], analysis: [],
            turnaround: "", report_deliverables: [], clinical_indications: [], limitations: "",
            public_notes: "", methodology: "", ordering_information: "", ...node })),
          offerings: [{ offering_id: "solid", title: "Solid", group_id: "solid", group_label: "Solid",
            diagnosis_id: "base", diagnosis_label: "No diagnosis / General testing",
            modality: "dna", family: "wgs", assay_id: "assay", assay_label: "Assay",
            description: entries.solid.description || parent.description || "", analysis: ["SNV"],
            price: entries.solid.price || parent.price || null, pricing_message: "Contact for pricing",
            turnaround: document.modalities.wgs.categories.solid.tat || "7-10 days",
            input_material: document.modalities.wgs.categories.solid.input_material || [], report_deliverables: ["PDF"],
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
    await expect(page.getByRole("button", { name: "Edit display name", exact: true })).toBeVisible()
    await expect(page.getByRole("button", { name: "Delete draft", exact: true })).toBeVisible()
    const saveBounds = await page.getByRole("button", { name: "Save draft", exact: true }).boundingBox()
    const previewBounds = await page.getByRole("button", { name: "Preview changes", exact: true }).boundingBox()
    expect(saveBounds!.height).toBeLessThanOrEqual(40)
    expect(previewBounds!.height).toBeLessThanOrEqual(40)
    expect(Math.abs(saveBounds!.y - previewBounds!.y)).toBeLessThanOrEqual(2)
    await page.screenshot({ path: `/tmp/catalog-simple-header-${theme}-${viewport.width}.png` })
    await page.getByRole("button", { name: "Add section", exact: true }).click()
    await expect(page.getByRole("heading", { name: "New section", exact: true })).toBeVisible()
    await expect(page.getByText("Add an entry or subsection to New section to preview the catalog.", { exact: true })).toBeVisible()
    // Exercise the idle debounce interval while the new section is still empty.
    await page.waitForTimeout(450)
    expect(invalidPreviewRequests).toBe(0)
    await page.getByRole("button", { name: "Add subsection", exact: true }).click()
    await expect(page.getByRole("heading", { name: "New subsection", exact: true })).toBeVisible()
    await page.getByRole("button", { name: "Add new entry under New subsection", exact: true }).click()
    await expect(page.getByRole("heading", { name: "New child", exact: true })).toBeVisible()
    const setup = page.getByRole("group", { name: "Entry setup", exact: true })
    await setup.getByRole("combobox", { name: "Assay", exact: true }).selectOption("assay")
    await setup.getByRole("combobox", { name: "Diagnosis", exact: true }).selectOption("assay_base")
    await setup.getByRole("checkbox", { name: "SNV", exact: true }).check()
    await setup.getByRole("combobox", { name: "Add gene list for SNV", exact: true }).selectOption("synthetic-genes")
    await expect(setup.getByRole("button", { name: "Remove Synthetic genes from SNV", exact: true })).toBeVisible()
    const sectionBranch = page.getByRole("navigation", { name: "Catalog levels", exact: true })
      .getByRole("button", { name: "New subsection", exact: true }).locator("..").locator("..")
    await expect(sectionBranch.getByRole("button", { name: "New child", exact: true })).toBeVisible()
    await expect(page.getByText("Source structure and unlinked entries", { exact: true })).toHaveCount(0)
    await setup.screenshot({ path: `/tmp/catalog-simple-setup-${theme}-${viewport.width}.png` })
    await page.getByRole("navigation", { name: "Catalog levels", exact: true })
      .screenshot({ path: `/tmp/catalog-simple-tree-${theme}-${viewport.width}.png` })
    const configuration = page.getByRole("group", { name: "Entry configuration", exact: true })
    expect(await configuration.evaluate(el => getComputedStyle(el).boxShadow)).not.toBe("none")
    await page.getByText("Entry structure and source settings", { exact: true }).click()
    await expect(page.getByLabel("Parent entry", { exact: true })).not.toHaveValue("")
    await page.screenshot({ path: `/tmp/catalog-new-subsection-${theme}-${viewport.width}.png`, fullPage: true })
    await page.getByRole("navigation", { name: "Catalog structure", exact: true }).getByRole("button", { name: "New section", exact: true }).click()
    await page.getByText("Section structure and source settings", { exact: true }).click()
    await page.getByRole("button", { name: "Remove section", exact: true }).click()
    const levels = page.getByRole("navigation", { name: "Catalog levels" })
    await levels.getByRole("button", { name: "WGS", exact: true }).click()
    await levels.getByRole("button", { name: "Solid", exact: true }).click()
    await levels.getByRole("button", { name: "No diagnosis / General testing", exact: true }).click()
    await levels.getByRole("button", { name: "No diagnosis / General testing", exact: true })
      .locator("..").locator("..").getByRole("button", { name: "Solid", exact: true }).click()
    await page.getByRole("button", { name: "Edit price", exact: true }).click()
    await page.getByRole("checkbox", { name: "Set a price at this level", exact: true }).check()
    await page.getByLabel("Currency (three-letter code)", { exact: true }).fill("SEK")
    await expect(page.getByRole("button", { name: "Save draft", exact: true })).toBeDisabled()
    await page.waitForTimeout(450)
    expect(invalidPreviewRequests).toBe(0)
    await expect(page.getByText("Request could not be completed", { exact: true })).toHaveCount(0)
    await page.getByRole("button", { name: "Cancel field edit", exact: true }).click()
    rejectPreview = true
    await page.getByRole("button", { name: "Edit subheading", exact: true }).click()
    await page.getByLabel("Subheading", { exact: true }).fill("Synthetic service information")
    await page.getByRole("button", { name: "Done", exact: true }).click()
    await expect(page.getByRole("button", { name: "Retry preview", exact: true })).toBeVisible()
    await expect(page.getByText("Request could not be completed", { exact: true })).toHaveCount(0)
    rejectPreview = false
    await page.getByRole("button", { name: "Retry preview", exact: true }).click()
    await expect(page.getByRole("button", { name: "Retry preview", exact: true })).toHaveCount(0)
    await page.getByRole("button", { name: "Edit input material", exact: true }).click()
    await page.getByRole("checkbox", { name: "RNA", exact: true }).check()
    await page.getByRole("button", { name: "Done", exact: true }).click()
    await page.getByRole("button", { name: "Edit turnaround", exact: true }).click()
    await expect(page.getByLabel("Turnaround value or range")).toHaveValue("7-10")
    await page.getByRole("button", { name: "Cancel field edit", exact: true }).click()
    await page.screenshot({ path: `/tmp/catalog-gene-editor-${theme}-${viewport.width}.png`, fullPage: true })
    await configuration.screenshot({ path: `/tmp/catalog-gene-configuration-${theme}-${viewport.width}.png` })
    await levels.locator('button[data-level="group"]').filter({ hasText: "Solid" }).click()
    await page.getByRole("button", { name: "Add shared defaults", exact: true }).click()
    await page.getByRole("button", { name: "Edit description", exact: true }).click()
    await page.getByRole("textbox", { name: "Description", exact: true }).fill("Parent group service information")
    await page.getByRole("button", { name: "Done", exact: true }).click()
    await page.getByRole("button", { name: "Edit price", exact: true }).click()
    await page.getByRole("checkbox", { name: "Set a price at this level", exact: true }).check()
    await page.getByLabel("Price amount", { exact: true }).fill("450")
    await page.getByLabel("Currency (three-letter code)", { exact: true }).fill("SEK")
    await page.getByRole("button", { name: "Done", exact: true }).click()
    await expect(page.getByText("Parent group service information", { exact: true })).toBeVisible()
    await expect(page.getByRole("region", { name: "Service information" }).getByText("1 unique gene in the published scope", { exact: true })).toBeVisible()
    expect(version.revision).toBe(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
    await page.screenshot({ path: `/tmp/catalog-builder-${theme}-${viewport.width}.png`, fullPage: true })
    await page.getByRole("button", { name: "Save draft", exact: true }).click()
    await expect(page.getByRole("region", { name: "Catalog preview" })).toBeVisible()
    await expect(page.getByLabel("Catalog heading")).toHaveCount(0)
    const preview = page.getByRole("region", { name: "Catalog preview" })
    await expect(preview.getByRole("navigation", { name: "Test categories" })).toBeVisible()
    await preview.getByRole("navigation", { name: "Test categories" }).getByRole("button", { name: "DNA", exact: true }).click()
    await preview.getByRole("navigation", { name: "Test categories" }).getByRole("button", { name: "WGS", exact: true }).click()
    await preview.getByRole("navigation", { name: "Test categories" }).getByRole("button", { name: "Solid", exact: true }).click()
    await preview.getByRole("navigation", { name: "Test categories" }).getByRole("button", { name: "No diagnosis / General testing", exact: true }).click()
    await expect(preview.getByText("TP53", { exact: true })).toBeVisible()
    await expect(preview.getByText("7-10 days", { exact: true })).toBeVisible()
    await expect(preview.getByText("RNA", { exact: true })).toBeVisible()
    await expect(preview.getByText("Parent group service information", { exact: true })).toBeVisible()
    await expect(preview.getByText(/450/)).toBeVisible()
    expect(await preview.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)")
    await page.screenshot({ path: `/tmp/catalog-preview-${theme}-${viewport.width}.png`, fullPage: true })
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
    await page.screenshot({ path: `/tmp/catalog-matrix-${theme}-${viewport.width}.png`, fullPage: true })
    await preview.getByRole("button", { name: "Catalog", exact: true }).click()
    await preview.getByRole("button", { name: "Catalog introduction" }).click()
    await expect(preview.getByRole("navigation", { name: "Test categories" })).toBeVisible()
  })
}
}
