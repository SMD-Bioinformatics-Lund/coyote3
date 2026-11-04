import { expect, test } from "@playwright/test"
import { installApiFixtures } from "./support/api-fixtures"
import type { Offering } from "../../src/pages/catalog/offering-types"

for (const theme of ["light", "dark"]) {
  for (const width of [390, 1440]) {
    test(`published catalog hierarchy in ${theme} at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 })
      const panel: Offering = {
        offering_id: "synthetic-mpn", title: "MPN", group_id: "hematology", group_label: "Hematology",
        diagnosis_id: "mpn", diagnosis_label: "MPN", modality: "dna", family: "panel-dna",
        assay_id: "synthetic-panel", assay_label: "Synthetic panel", description: "MPN clinical service",
        analysis: ["SNV", "CNV"], price: null, pricing_message: "Contact for pricing",
        turnaround: "14 days", input_material: ["DNA", "Fresh", "Fresh Frozen", "Blood", "Bone marrow", "FFPE", "Other Neoplastic Tissue"], report_deliverables: ["PDF"],
        sample_modes: ["Tumor-normal"], platform: "Synthetic sequencer", read_length: 150,
        read_mode: "paired-end", covered_gene_count: 25,
        methodology: "Targeted sequencing", limitations: "Validated regions only",
        ordering_information: "Contact the center before submitting",
        gene_scopes: [
          { list_id: "mpn", label: "MPN genes", revision: 2, analysis: "SNV", genes: ["TP53"], excluded_gene_count: 1 },
          { list_id: "cnv", label: "CNV genes", revision: 1, analysis: "CNV", genes: ["MYC"], excluded_gene_count: 0 },
        ],
      }
      const node = (node_id: string, label: string, parent_id: string | null, description: string) => ({
        node_id, parent_id, label, title: label, description, offering_id: null,
        subheading: "", input_material: [], sample_modes: [], analysis: [], turnaround: "",
        report_deliverables: [], clinical_indications: [], limitations: "", public_notes: "",
        methodology: "", ordering_information: "",
      })
      const publication = {
        version: 3, header: "Synthetic assay catalog", description: "Our published genomic services",
        offerings: [panel], navigation: [
          node("dna", "DNA", null, "DNA overview"),
          node("panels", "Panels", "dna", "Panel overview"),
          node("hema", "Hematology", "panels", "Parent hematology information"),
          { ...node("mpn", "MPN", "hema", "MPN clinical service"), offering_id: panel.offering_id },
          node("rna", "RNA", null, "RNA overview"),
        ],
      }
      await installApiFixtures(page, path => {
        if (path.endsWith("/auth/whoami")) return { json: {
          username: "synthetic-viewer", roles: ["user"], permissions: [], ui_settings: { theme },
        } }
        if (path.endsWith("/assay-catalog/offerings")) return { json: publication }
        if (path.endsWith("/asp/synthetic-panel/genes")) return { json: { gene_details: [
          { hgnc_symbol: "TP53", gene_name: "tumor protein p53", chromosome: "17",
            refseq_mane_plus_clinical: ["NM_000546.6"], ensembl_mane_select: "ENST00000269305.9" },
          { hgnc_symbol: "MYC", gene_name: "MYC proto-oncogene", chromosome: "8" },
          { hgnc_symbol: "OUTSIDE", gene_name: "Not part of this publication" },
        ] } }
      })
      await page.goto("/public/catalog")
      const tree = page.getByRole("navigation", { name: "Test categories" })
      await expect(page.getByText("Our published genomic services")).toBeVisible()
      await expect(page.getByRole("region", { name: "Catalog overview" })).toBeVisible()
      await expect(page.getByRole("region", { name: "Service information" })).toHaveCount(0)
      await page.screenshot({ path: testInfo.outputPath(`introduction-${theme}-${width}.png`), fullPage: true })
      for (const [label, description] of [["DNA", "DNA overview"], ["Panels", "Panel overview"], ["Hematology", "Parent hematology information"]]) {
        await tree.getByRole("button", { name: label, exact: true }).click()
        await expect(page.getByText(description, { exact: true })).toBeVisible()
        if (label === "DNA") {
          const overview = page.getByRole("region", { name: "Catalog overview" })
          await expect(overview.getByText("MPN clinical service", { exact: true })).toHaveCount(0)
          await expect(overview.getByText("Turnaround (TAT)", { exact: true })).toHaveCount(0)
          await page.screenshot({ path: testInfo.outputPath(`modality-${theme}-${width}.png`), fullPage: true })
        }
      }
      await tree.getByRole("button", { name: "MPN", exact: true }).focus()
      await page.keyboard.press("Enter")
      await expect(page.getByRole("heading", { name: "MPN", exact: true })).toBeVisible()
      const service = page.getByRole("region", { name: "Service information" })
      const levels = await tree.locator(".catalog-tree-node").evaluateAll(elements =>
        Object.fromEntries(elements.filter(el => el.getAttribute("data-level")).map(el => {
          const style = getComputedStyle(el)
          return [el.getAttribute("data-level"), { size: parseFloat(style.fontSize), background: style.backgroundColor }]
        })))
      expect(levels.modality.size).toBeGreaterThan(levels.family.size)
      expect(levels.family.size).toBeGreaterThan(levels.group.size)
      expect(levels.group.size).toBeGreaterThan(levels.diagnosis.size)
      expect(new Set([levels.modality.background, levels.family.background, levels.group.background]).size).toBe(3)
      const badgeStyle = async (selector: string) => service.locator(selector).first().evaluate(el => {
        const style = getComputedStyle(el)
        return { background: style.backgroundColor, shadow: style.boxShadow }
      })
      const snvBadge = await badgeStyle(".badge-snv")
      const cnvBadge = await badgeStyle(".badge-cnv")
      expect(snvBadge.background).not.toBe(cnvBadge.background)
      expect(snvBadge.shadow).not.toBe("none")
      expect(cnvBadge.shadow).not.toBe("none")
      const tissueStyles = await service.locator("[data-material]").evaluateAll(elements => elements.map(el => {
        const style = getComputedStyle(el)
        return { background: style.backgroundColor, shadow: style.boxShadow }
      }))
      expect(new Set(tissueStyles.map(style => style.background)).size).toBe(6)
      expect(tissueStyles.every(style => style.shadow !== "none")).toBe(true)
      const factStyles = await Promise.all(["price", "turnaround", "coverage"].map(kind => badgeStyle(`[data-kind="${kind}"]`)))
      expect(new Set(factStyles.map(style => style.background)).size).toBe(3)
      expect(factStyles.every(style => style.shadow !== "none")).toBe(true)
      const essentials = service.getByRole("group", { name: "Service essentials" })
      for (const kind of ["price", "turnaround"]) {
        const badge = essentials.locator(`[data-kind="${kind}"]`)
        await expect(badge).toBeVisible()
        const badgeBox = await badge.boundingBox()
        const snvBox = await service.locator(".badge-snv").boundingBox()
        expect(badgeBox!.height).toBeGreaterThan(snvBox!.height * 1.5)
      }
      if (width === 1440) {
        const summaryBox = await service.boundingBox()
        const essentialsBox = await essentials.boundingBox()
        expect(essentialsBox!.x).toBeGreaterThan(summaryBox!.x + summaryBox!.width * 0.4)
        expect(essentialsBox!.y).toBeLessThan(summaryBox!.y + 100)
      }
      await expect(page.getByText("Targeted sequencing", { exact: true })).toBeVisible()
      await expect(page.getByText("Contact the center before submitting")).toBeVisible()
      await expect(service.getByText("Price", { exact: true })).toBeVisible()
      await expect(service.getByText("2 unique genes in the published scope")).toBeVisible()
      await expect(service.getByText("Tumor-normal", { exact: true })).toBeVisible()
      await expect(service.getByText("Synthetic sequencer", { exact: true })).toBeVisible()
      await expect(page.getByRole("navigation", { name: "Entries in this section" })).toHaveCount(0)
      await expect(page.getByText("tumor protein p53", { exact: true })).toBeVisible()
      await expect(page.getByRole("cell").filter({ hasText: "NM_000546.6" })).toContainText("RS MC+")
      await expect(page.getByRole("columnheader", { name: /Published gene lists/ })).toHaveCount(0)
      await expect(page.getByText("Not part of this publication")).toHaveCount(0)
      expect(await service.evaluate(element => getComputedStyle(element).boxShadow)).not.toBe("none")
      expect(await service.evaluate(element => Boolean(element.compareDocumentPosition(document.querySelector('[role="tabpanel"]')!) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true)
      await expect(page.getByRole("button", { name: "View details" })).toHaveCount(0)
      await expect(page.getByLabel("Requested genes")).toHaveCount(0)
      await expect(page.getByRole("tab", { name: /SNV/ })).toHaveAttribute("aria-selected", "true")
      await page.screenshot({ path: testInfo.outputPath(`catalog-${theme}-${width}.png`), fullPage: true })
      await page.getByRole("tab", { name: /CNV/ }).focus()
      await page.keyboard.press("Enter")
      await expect(page.getByRole("tabpanel").getByRole("link", { name: "MYC", exact: true })).toBeVisible()
      await expect(page.getByRole("tabpanel").getByRole("link", { name: "TP53", exact: true })).toHaveCount(0)
      await tree.getByRole("button", { name: "Collapse Panels", exact: true }).click()
      await expect(page.getByRole("heading", { name: "MPN", exact: true })).toBeVisible()
      await tree.getByRole("button", { name: "Expand Panels", exact: true }).click()
      await tree.getByRole("button", { name: "Hematology", exact: true }).click()
      await expect(page.getByText("Parent hematology information")).toBeVisible()
      await expect(page.getByRole("tabpanel")).toHaveCount(0)
      await expect(page.getByRole("region", { name: "Service information" }).getByText("14 days", { exact: true })).toBeVisible()
      await expect(page.getByRole("region", { name: "Service information" }).getByText("Price", { exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`parent-overview-${theme}-${width}.png`), fullPage: true })
      await page.goBack()
      await expect(page.getByRole("heading", { name: "MPN", exact: true })).toBeVisible()
      await page.reload()
      await expect(page.getByRole("heading", { name: "MPN", exact: true })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()

      // Reproduce the deployed catalog's flat DNA -> assay/diagnosis authoring entries.
      publication.offerings = [panel,
        { ...panel, offering_id: "second-mpn", title: "Second MPN assay", assay_label: "Second panel", description: "Second exact MPN information",
          price: { amount: "450.00", currency: "SEK", kind: "fixed", conditions: "" } },
        { ...panel, offering_id: "wgs-mpn", family: "wgs", description: "Wrong method information" },
        { ...panel, offering_id: "myeloid-mpn", group_id: "myeloid", group_label: "Myeloid", description: "Wrong group information" },
        { ...panel, offering_id: "hema-cll", diagnosis_id: "cll", diagnosis_label: "CLL", description: "Wrong diagnosis information" },
        { ...panel, offering_id: "rna-mpn", modality: "rna", family: "panel-rna", description: "Wrong modality information" },
        { ...panel, offering_id: "wts-mpn", modality: "rna", family: "wts", description: "RNA transcriptome service" },
      ]
      publication.navigation = [node("dna", "DNA", null, "DNA overview"), node("rna", "RNA", null, "RNA overview"),
        ...publication.offerings.map(item => ({
          ...node(item.offering_id, `${item.title} / ${item.diagnosis_label}`, item.modality, item.description),
          offering_id: item.offering_id,
        })),
      ]
      await page.goto("/public/catalog")
      await expect(tree.getByRole("button", { name: "WGS", exact: true })).toBeVisible()
      const dnaBranch = tree.getByRole("listitem").filter({ has: page.getByRole("button", { name: "DNA", exact: true }) })
      await dnaBranch.getByRole("button", { name: "Panels", exact: true }).click()
      await dnaBranch.getByRole("button", { name: "Hematology", exact: true }).click()
      await dnaBranch.getByRole("button", { name: "MPN", exact: true }).click()
      await expect(page.getByRole("article")).toHaveCount(2)
      await expect(page.getByText("MPN clinical service", { exact: true })).toBeVisible()
      await expect(page.getByText("Second exact MPN information", { exact: true })).toBeVisible()
      for (const text of ["Wrong method information", "Wrong group information", "Wrong diagnosis information", "Wrong modality information"]) {
        await expect(page.getByText(text, { exact: true })).toHaveCount(0)
      }
      await expect(tree.getByRole("button", { name: "Second MPN assay / MPN", exact: true })).toHaveCount(0)
      const rnaBranch = tree.getByRole("listitem").filter({ has: page.getByRole("button", { name: "RNA", exact: true }) })
      await expect(rnaBranch.getByRole("button", { name: "Panels", exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`flat-hierarchy-${theme}-${width}.png`), fullPage: true })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
      await page.getByRole("button", { name: "Compare assays", exact: true }).click()
      await expect(page.getByRole("heading", { name: "Compare assays", exact: true })).toBeVisible()
      await page.goto("/public/catalog/compare?compare=synthetic-mpn&compare=second-mpn")
      const comparison = page.getByRole("table", { name: "Published service comparison" })
      await expect(comparison.getByRole("rowheader", { name: "Price", exact: true })).toBeVisible()
      await expect(comparison.getByText(/450/)).toBeVisible()
      await expect(comparison.getByRole("rowheader", { name: "Sample modes", exact: true })).toBeVisible()
      await expect(comparison.getByText("150 bp · paired-end", { exact: true })).toHaveCount(2)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy()
      await page.screenshot({ path: testInfo.outputPath(`comparison-${theme}-${width}.png`), fullPage: true })
      const surfaces = []
      for (const [path, token] of [
        [["dna"], "--color-dna"], [["rna"], "--color-rna"],
        [["dna", "panel-dna"], "--color-panel-dna"], [["dna", "wgs"], "--color-wgs"],
        [["rna", "panel-rna"], "--color-panel-rna"], [["rna", "wts"], "--color-wts"],
      ] as const) {
        await page.goto(`/public/catalog?node=${encodeURIComponent(JSON.stringify(path))}`)
        const panel = page.getByRole("region", { name: path.length === 1 ? "Catalog overview" : "Service information" })
        await expect(panel).toBeVisible()
        const style = await panel.evaluate((el, token) => {
          const style = getComputedStyle(el)
          return { accent: style.getPropertyValue("--catalog-family").trim(),
            expected: style.getPropertyValue(token).trim(), background: style.backgroundImage,
            shadow: style.boxShadow }
        }, token)
        expect(style.accent).toBe(style.expected)
        expect(style.shadow).not.toBe("none")
        expect(style.background).not.toBe("none")
        surfaces.push(style.background)
        if (width === 1440) await page.screenshot({ path: testInfo.outputPath(`surface-${path.join("-")}-${theme}.png`), fullPage: true })
      }
      // RNA and WTS intentionally share their established sequencing color.
      expect(new Set(surfaces).size).toBeGreaterThanOrEqual(5)
      await page.goto(`/public/catalog?node=${encodeURIComponent(JSON.stringify(["dna", "panel-dna", "hematology", "mpn"]))}`)
      await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" })
      const selectedNode = tree.locator('[aria-current="page"]')
      await expect(selectedNode).toHaveCount(1)
      const accessibleStyle = await selectedNode.evaluate(el => {
        const style = getComputedStyle(el)
        return { background: style.backgroundImage, shadow: style.boxShadow, transition: style.transitionDuration }
      })
      expect(accessibleStyle.background).toBe("none")
      expect(accessibleStyle.shadow).toBe("none")
      const accessiblePanel = page.getByRole("region", { name: "Service information" })
      expect(await accessiblePanel.evaluate(el => getComputedStyle(el).backgroundImage)).toBe("none")
      expect(await accessiblePanel.evaluate(el => getComputedStyle(el).boxShadow)).toBe("none")
      const accessibleBadges = await accessiblePanel.locator('[data-kind="price"]').evaluateAll(elements =>
        elements.map(el => getComputedStyle(el).boxShadow))
      expect(accessibleBadges.length).toBeGreaterThan(0)
      expect(accessibleBadges.every(shadow => shadow === "none")).toBe(true)
      // The shared reduced-motion policy caps transitions at 0.01 ms.
      expect(parseFloat(accessibleStyle.transition)).toBeLessThanOrEqual(0.00001)
    })
  }
}
