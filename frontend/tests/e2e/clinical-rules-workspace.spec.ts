import { expect, test } from "@playwright/test"
import { readFile } from "node:fs/promises"

import { installApiFixtures } from "./support/api-fixtures"

const ruleSet = {
  _id: "rule-version-1",
  rule_set_id: "assay_1__base__sv",
  schema_version: 1,
  content_version: 1,
  revision: 1,
  scope: { asp_id: "assay_1", diagnosis_id: "base", analyte: "dna", language: "sv" },
  name: "Assay 1 report rules",
  status: "draft",
  active: false,
  analysis_declarations: { SNV: { narrative: "enabled" } },
  terminology: {},
  blocks: [{
    block_id: "report_summary",
    name: "Report summary",
    analysis: "SNV",
    evaluation: { mode: "once", collection: null },
    section: "Report summary",
    section_order: 100,
    block_order: 10,
    show_heading: true,
    match_strategy: "at_most_one",
    conflict_group: null as string | null,
    rules: [{ rule_id: "summary", name: "Summary", order: 10, enabled: true, condition: null, output: [{ type: "text", value: "No reportable findings." }], references: [] }],
  }],
  test_cases: [],
  references: [],
  change_summary: "",
  review: {},
  updated_at: "2026-09-05T12:00:00Z",
  updated_by: "admin",
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [390, 1440]) {
    for (const initialStatus of ["submitted", "in_clinical_review", "approved"]) {
      test(`${initialStatus} rules can return to review: ${theme}, ${width}px`, async ({ page }) => {
        await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
        await page.setViewportSize({ width, height: 1000 })
        let saved = { ...structuredClone(ruleSet), status: initialStatus }
        await installApiFixtures(page, (path, _url, route) => {
          if (path.endsWith("/auth/whoami")) return { json: { username: "author", roles: ["admin"], ui_settings: { theme }, permissions: ["clinical_rules:view", "clinical_rules:draft", "clinical_rules:submit", "clinical_rules:publish"] } }
          if (path.endsWith("/reopen")) {
            expect(route.request().postDataJSON().revision).toBe(saved.revision)
            saved = { ...saved, status: "draft", revision: saved.revision + 1, review: {} }
            return { json: saved }
          }
          if (path.endsWith("/drafts/rule-version-1")) {
            expect(saved.status).toBe("draft")
            saved = { ...saved, ...route.request().postDataJSON(), revision: saved.revision + 1 }
            return { json: saved }
          }
          if (path.endsWith("/submit")) {
            expect(saved.status).toBe("draft")
            expect(route.request().postDataJSON().assignee).toBe("reviewer")
            saved = { ...saved, status: "submitted", revision: saved.revision + 1 }
            return { json: saved }
          }
          if (path.endsWith("/versions/rule-version-1")) return { json: saved }
          if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [saved], total: 1 } }
          if (path.endsWith("/authoring-options")) return { json: { assays: [], clinical_reviewers: [{ username: "reviewer", name: "Reviewer" }] } }
          if (path.endsWith("/facts")) return { json: { items: [] } }
        })
        await page.goto("/admin/clinical-rules")
        await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
        await expect(page.getByLabel("Clinical rule name")).toBeDisabled()
        if (initialStatus === "approved") await expect(page.getByRole("button", { name: "Publish", exact: true })).toBeVisible()
        else await expect(page.getByRole("button", { name: "Publish", exact: true })).toHaveCount(0)
        await page.getByRole("button", { name: initialStatus === "approved" ? "Edit again" : "Recall and edit", exact: true }).click()
        await expect(page.getByLabel("Clinical rule name")).toBeEnabled()
        await expect(page.getByRole("button", { name: "Publish", exact: true })).toHaveCount(0)
        await page.getByLabel("Clinical rule name").fill("Changed after recall")
        await expect.poll(() => saved.blocks[0].rules[0].name).toBe("Changed after recall")
        await page.getByLabel("Assign clinical reviewer").selectOption("reviewer")
        await page.getByRole("button", { name: "Submit", exact: true }).click()
        await expect.poll(() => saved.status).toBe("submitted")
        await expect(page.getByLabel("Clinical rule name")).toBeDisabled()
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
      })
    }

    test(`bulk annotation workspace: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      let saved = { ...structuredClone(ruleSet), bulk_annotation_rules: [{
        rule_id: "gene_annotation", name: "Gene annotation", tier: 2, order: 10,
        enabled: true, condition: { type: "predicate", fact: "finding.gene", operator: "eq", value: "GENE_A" },
        output: [{ type: "text", value: "Reviewed gene annotation." }], references: [],
      }] }
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "admin", roles: ["admin"], ui_settings: { theme }, permissions: ["clinical_rules:view", "clinical_rules:draft"] } }
        if (path.endsWith("/drafts/rule-version-1")) {
          saved = { ...saved, ...route.request().postDataJSON(), revision: saved.revision + 1 }
          return { json: saved }
        }
        if (path.endsWith("/bulk-annotations/preview")) {
          const facts = route.request().postDataJSON() as { gene: string; tier: number }
          return { json: facts.gene === "GENE_A" && facts.tier === 2
            ? { rule_id: "gene_annotation", text: "**Reviewed** GENE_A" }
            : { rule_id: null, text: null } }
        }
        if (path.endsWith("/versions/rule-version-1")) return { json: saved }
        if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [saved], total: 1 } }
        if (path.endsWith("/authoring-options")) return { json: { assays: [], bulk_annotation_fact_paths: ["finding.gene"] } }
        if (path.endsWith("/facts")) return { json: { items: [{ path: "finding.gene", label: "Gene", kind: "string", group: "Finding", operators: ["eq", "in"], scopes: ["each_finding"] }] } }
      })
      await page.goto("/admin/clinical-rules")
      await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
      await page.getByRole("tab", { name: "Report wording" }).focus()
      await page.keyboard.press("ArrowRight")
      await expect(page.getByRole("tab", { name: "Bulk annotation text" })).toHaveAttribute("aria-selected", "true")
      await page.getByRole("button", { name: "Tier II", exact: true }).click()
      await expect(page.getByLabel("Annotation template name")).toHaveValue("Gene annotation")
      await expect(page.getByRole("option", { name: "Find in collection", exact: true })).toHaveCount(0)
      const sentence = page.getByLabel("Annotation sentence", { exact: true })
      await sentence.fill("**Reviewed** {{finding.gene}}")
      await expect.poll(() => JSON.stringify(saved.bulk_annotation_rules)).toContain('"path":"finding.gene"')
      await page.getByLabel("Annotation preview Gene", { exact: true }).fill("GENE_A")
      await expect(page.getByLabel("Annotation preview Diagnosis", { exact: true })).toHaveValue("base")
      await page.getByLabel("Annotation preview Diagnosis", { exact: true }).fill("scope_a")
      const previewRequest = page.waitForRequest(request => request.url().endsWith("/bulk-annotations/preview"))
      await page.getByRole("button", { name: "Preview annotation", exact: true }).click()
      expect((await previewRequest).postDataJSON().diagnosis_id).toBe("scope_a")
      await expect(page.getByRole("region", { name: "Bulk annotation preview" }).locator("strong")).toHaveText("Reviewed")
      await page.getByLabel("Annotation preview Gene", { exact: true }).fill("GENE_B")
      await page.getByRole("button", { name: "Preview annotation", exact: true }).click()
      await expect(page.getByText(/No enabled template matched/)).toBeVisible()
      await page.getByRole("tab", { name: "Report wording" }).click()
      await expect(page.getByLabel("Clinical rule name")).toHaveValue("Summary")
      await page.getByRole("tab", { name: "Bulk annotation text" }).click()
      await expect(sentence).toHaveValue("**Reviewed** {{finding.gene}}")
      await page.getByText("Version notes", { exact: true }).click()
      await page.getByLabel("Change summary", { exact: true }).fill("Reviewed gene-specific bulk wording.")
      await expect.poll(() => saved.change_summary).toBe("Reviewed gene-specific bulk wording.")
      await page.getByText("Version notes", { exact: true }).click()
      await page.getByRole("tab", { name: "Bulk annotation text" }).scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath("bulk-annotation-workspace.png"), fullPage: true })
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    })

    test(`existing rules can be reordered: ${theme}, ${width}px`, async ({ page }) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      let saved = structuredClone(ruleSet)
      const originalRules = ["First", "Second", "Third"].map((name, index) => ({
        ...structuredClone(ruleSet.blocks[0].rules[0]),
        rule_id: name.toLowerCase(), name, order: (index + 1) * 100,
        output: [{ type: "text", value: `${name} sentence.` }],
      }))
      saved.blocks[0].rules = structuredClone(originalRules)
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "admin", roles: ["admin"], ui_settings: { theme }, permissions: ["clinical_rules:view", "clinical_rules:draft"] } }
        if (path.endsWith("/drafts/rule-version-1")) {
          saved = { ...saved, ...route.request().postDataJSON(), revision: saved.revision + 1 }
          return { json: saved }
        }
        if (path.endsWith("/versions/rule-version-1")) return { json: saved }
        if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [saved], total: 1 } }
        if (path.endsWith("/authoring-options")) return { json: { assays: [] } }
        if (path.endsWith("/facts")) return { json: { items: [] } }
      })
      await page.goto("/admin/clinical-rules")
      await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
      const up = page.getByRole("button", { name: "Move rule up", exact: true })
      const down = page.getByRole("button", { name: "Move rule down", exact: true })
      await expect(up).toBeDisabled()
      await down.focus()
      await page.keyboard.press("Enter")
      await expect(page.getByLabel("Clinical rule name")).toHaveValue("First")
      await expect.poll(() => saved.blocks[0].rules.map(item => item.rule_id)).toEqual(["second", "first", "third"])
      await expect(page.getByLabel("Section rules").getByRole("button", { name: "First", exact: true })).toHaveAttribute("aria-pressed", "true")
      await down.click()
      await expect(down).toBeDisabled()
      await expect.poll(() => saved.blocks[0].rules.map(item => item.order)).toEqual([10, 20, 30])
      await expect.poll(() => saved.blocks[0].rules.map(item => item.rule_id)).toEqual(["second", "third", "first"])
      for (const original of originalRules) {
        expect(saved.blocks[0].rules.find(item => item.rule_id === original.rule_id)).toEqual({ ...original, order: saved.blocks[0].rules.find(item => item.rule_id === original.rule_id)?.order })
      }
      await up.click()
      await expect.poll(() => saved.blocks[0].rules.map(item => item.rule_id)).toEqual(["second", "first", "third"])
      await page.reload()
      await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
      await expect(page.getByLabel("Section rules").getByRole("button").filter({ hasText: /^(First|Second|Third)$/ })).toHaveText(["Second", "First", "Third"])
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    })

    test(`rule Markdown keeps dynamic values: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      let saved = structuredClone(ruleSet)
      await installApiFixtures(page, (path, _url, route) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "admin", roles: ["admin"], ui_settings: { theme }, permissions: ["clinical_rules:view", "clinical_rules:draft"] } }
        if (path.endsWith("/drafts/rule-version-1")) {
          saved = { ...saved, ...route.request().postDataJSON(), revision: saved.revision + 1 }
          return { json: saved }
        }
        if (path.endsWith("/versions/rule-version-1")) return { json: saved }
        if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [saved], total: 1 } }
        if (path.endsWith("/authoring-options")) return { json: { assays: [] } }
        if (path.endsWith("/facts")) return { json: { items: [{ path: "asp.display_name", label: "Assay name", kind: "string", group: "Assay", operators: ["eq"], scopes: ["once"] }] } }
      })
      await page.goto("/admin/clinical-rules")
      await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
      if (theme === "dark") await expect(page.locator("html")).toHaveClass(/dark/)
      else await expect(page.locator("html")).not.toHaveClass(/dark/)
      const input = page.getByLabel("Report sentence", { exact: true })
      await expect(page.getByRole("note", { name: "Missing clinical rule tests" })).toHaveCount(0)
      await input.fill("**Evidence** for {{asp.display_name}}\n\n- Reviewed scope")
      await expect.poll(() => JSON.stringify(saved.blocks)).toContain('"path":"asp.display_name"')
      await input.locator("..").getByRole("button", { name: "Preview", exact: true }).click()
      const rendered = page.getByLabel("Report sentence preview", { exact: true })
      await expect(rendered.locator("strong")).toHaveText("Evidence")
      await expect(rendered.getByRole("listitem")).toHaveText("Reviewed scope")
      await rendered.locator("..").getByRole("button", { name: "Write", exact: true }).focus()
      await page.keyboard.press("Enter")
      await expect(input).toHaveValue("**Evidence** for {{asp.display_name}}\n\n- Reviewed scope")
      await input.locator("..").screenshot({ path: testInfo.outputPath("markdown-editor.png") })
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1)
    })

    test(`rule export metadata is opt-in: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.addInitScript(value => localStorage.setItem("vite-ui-theme", value), theme)
      await page.setViewportSize({ width, height: 1000 })
      const portable = { schema_version: 1, scope: ruleSet.scope, name: ruleSet.name,
        analysis_declarations: ruleSet.analysis_declarations, blocks: ruleSet.blocks,
        terminology: {}, test_cases: [], references: [] }
      await installApiFixtures(page, (path, url) => {
        if (path.endsWith("/auth/whoami")) return { json: { username: "admin", roles: ["admin"], ui_settings: { theme }, permissions: ["clinical_rules:view"] } }
        if (path.endsWith("/export")) return { json: url.searchParams.get("include_metadata") === "true" ? ruleSet : portable }
        if (path.endsWith("/versions/rule-version-1")) return { json: ruleSet }
        if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [ruleSet], total: 1 } }
        if (path.endsWith("/facts")) return { json: { items: [] } }
        if (path.endsWith("/authoring-options")) return { json: { assays: [] } }
      })
      await page.goto("/admin/clinical-rules")
      await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
      const metadata = page.getByRole("checkbox", { name: "Include metadata" })
      const exportButton = page.getByRole("button", { name: "Export JSON" })
      await expect(metadata).not.toBeChecked()
      await expect(metadata).toBeInViewport()
      for (const include of [false, true]) {
        if (include) { await metadata.focus(); await metadata.press("Space") }
        const downloaded = page.waitForEvent("download")
        await exportButton.click()
        const file = await (await downloaded).path()
        if (!file) throw new Error("Expected a downloaded JSON file")
        const content = JSON.parse(await readFile(file, "utf8"))
        expect(content.blocks).toEqual(ruleSet.blocks)
        expect("content_version" in content).toBe(include)
        expect("updated_by" in content).toBe(include)
        expect("_id" in content).toBe(include)
      }
      await exportButton.locator("..").screenshot({ path: testInfo.outputPath("export-controls.png") })
    })
  }
}

test("composition preview separates conditional wording in a narrow report pane", async ({ page }) => {
  const document = {
    ...structuredClone(ruleSet),
    blocks: [{ ...ruleSet.blocks[0], match_strategy: "all_matches", show_heading: false, rules: [
      { ...ruleSet.blocks[0].rules[0], name: "General introduction", output: [{ type: "text", value: "DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering." }] },
      ...[true, false].map((paired, index) => ({
        ...ruleSet.blocks[0].rules[0], rule_id: `control_${index}`, order: 20 + index,
        name: paired ? "Paired control wording" : "Unpaired control wording", presentation: "continue",
        condition: { type: "predicate", fact: "sample.paired", operator: "eq", value: paired },
        output: [{ type: "text", value: paired ? "Hudbiopsi har använts som kontrollmaterial." : "Analysen avser somatiska mutationer utan parat kontrollprov." }],
      })),
    ] }],
  }
  await installApiFixtures(page, (path) => {
    if (path === "/api/v1/auth/whoami") return { json: { username: "admin", roles: ["admin"], permissions: ["clinical_rules:view", "clinical_rules:draft", "clinical_rules:test"] } }
    if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [document], page: 1, total: 1 } }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1") return { json: document }
    if (path.endsWith("/test-samples")) return { json: { items: [] } }
    if (path.endsWith("/facts")) return { json: { items: [{ path: "sample.paired", label: "Paired control available", group: "Sample", kind: "boolean", operators: ["eq"], scopes: ["once"] }] } }
    if (path.endsWith("/authoring-options")) return { json: { assays: [{ asp_id: "assay_1", display_name: "Assay 1", analyte: "dna" }] } }
  })
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.goto("/admin/clinical-rules")
  await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
  const preview = page.getByRole("region", { name: "Complete rule-set preview" })
  await expect(preview.getByRole("article")).toHaveCount(3)
  const paired = preview.getByRole("article", { name: "Paired control wording", exact: true })
  await expect(paired.getByText("Hudbiopsi har använts som kontrollmaterial.")).toBeVisible()
  await paired.getByText("When this sentence applies").click()
  await expect(paired.getByText("Paired control available is Yes")).toBeVisible()
  await page.screenshot({ path: "test-results/clinical-rule-composition-preview.png", fullPage: true })
  await preview.getByLabel("Show conditional wording").uncheck()
  await expect(paired.getByText("Hudbiopsi har använts som kontrollmaterial.")).toHaveCount(0)
  await expect(preview.getByRole("article")).toHaveCount(3)
  await preview.getByLabel("Show conditional wording").check()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(paired.getByText("Hudbiopsi har använts som kontrollmaterial.")).toBeVisible()
  await expect(preview).toHaveJSProperty("scrollWidth", await preview.evaluate(element => element.clientWidth))
})

test("clinical rule panes fill the workspace and reflow into selectable rails", async ({ page }) => {
  let savedRuleSet = structuredClone(ruleSet)
  await installApiFixtures(page, (path, _url, route) => {
    if (path === "/api/v1/admin/clinical-rule-sets/drafts/rule-version-1") {
      savedRuleSet = { ...savedRuleSet, ...route.request().postDataJSON(), revision: savedRuleSet.revision + 1 }
      return { json: savedRuleSet }
    }
    if (path === "/api/v1/auth/whoami") return { json: { username: "admin", role: "admin", roles: ["admin"], access_level: 99_999, permissions: ["clinical_rules:view", "clinical_rules:draft", "clinical_rules:test"] } }
    if (path === "/api/v1/admin/clinical-rule-sets/facts") return { json: { items: [
      { path: "gene_lists.snv.ids", label: "SNV selected lists: identifiers", group: "Gene lists", kind: "string_list", operators: ["contains", "exists"], scopes: ["once"] },
      { path: "asp.display_name", label: "Assay full display name", group: "Assay", kind: "string", operators: ["eq"], scopes: ["once"] },
      { path: "asp.covered_genes_count", label: "Assay covered gene count", group: "Assay", kind: "integer", operators: ["eq"], scopes: ["once"] },
    ] } }
    if (path === "/api/v1/admin/clinical-rule-sets/authoring-options") return { json: { assays: [{ asp_id: "assay_1", display_name: "Assay 1", analyte: "dna" }] } }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1") return { json: savedRuleSet }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1/test-samples") return { json: { items: [] } }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1/revisions") return { json: { items: [{ rule_set_oid: ruleSet._id, rule_set_id: ruleSet.rule_set_id, content_version: 1, revision: 1, action: "draft_created", actor: "admin", occurred_at: "2026-09-05T12:00:00Z", revision_hash: "a".repeat(64), document: ruleSet }] } }
    if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [ruleSet], page: 1, per_page: 30, total: 1 } }
  })

  await page.goto("/admin/clinical-rules")
  await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
  await expect(page.locator("aside").getByText("No reportable findings.")).toBeVisible()
  await expect(page.getByLabel("Report sentence")).toBeVisible()
  await page.getByRole("button", { name: "Add condition", exact: true }).click()
  await page.getByLabel("Condition operator").selectOption("exists")
  await expect.poll(() => savedRuleSet.blocks[0].rules[0].condition).toMatchObject({ operator: "exists", value: true })
  await page.getByLabel("Report sentence").fill("Panel {{asp.display_name}} covers {{asp.covered_genes_count}} genes.")
  await expect.poll(() => JSON.stringify(savedRuleSet.blocks[0].rules[0].output)).toContain('"type":"number"')

  const workspace = page.locator(".clinical-rules-workspace")
  const builder = workspace.locator(":scope > main")
  const initialBuilder = await builder.boundingBox()
  await page.getByRole("button", { name: "Collapse rule-set list" }).click()
  await page.getByRole("button", { name: "Collapse report sections" }).click()

  await expect(page.getByRole("button", { name: "Select section Report summary" })).toBeVisible()
  const collapsedBuilder = await builder.boundingBox()
  const workspaceBox = await workspace.boundingBox()
  expect(workspaceBox?.height).toBeGreaterThan(600)
  expect(collapsedBuilder?.width).toBeGreaterThan(initialBuilder?.width || 0)
  await expect(page.getByRole("heading", { name: "Complete report text" })).toBeVisible()
  await page.setViewportSize({ width: 1600, height: 1050 })
  await page.screenshot({ path: "test-results/clinical-rule-sentence-desktop.png", fullPage: true })
  await page.getByText("Version notes", { exact: true }).click()
  await page.getByRole("button", { name: /Revision history/ }).click()
  await expect(page.getByText("draft created")).toBeVisible()
  await expect(page.getByText("First preserved revision")).toBeVisible()
  await page.getByText("Version notes", { exact: true }).click()
  await page.getByText("Section settings", { exact: true }).click()
  await page.getByLabel("Output destination").selectOption("analysis_description")
  await expect(page.getByLabel("Section", { exact: true })).toHaveValue("Analysis description")
  await expect(page.getByLabel("Match behavior")).toHaveValue("all_matches")
  await expect(page.getByLabel("Show section heading")).toBeDisabled()
  await expect(page.getByLabel("Report sentence")).toBeVisible()
  await page.getByLabel("Report sentence").focus()
  await expect(page.getByLabel("Report sentence")).toBeFocused()
  await page.evaluate(() => document.documentElement.classList.remove("dark"))
  await page.screenshot({ path: "test-results/analysis-description-wide-light.png", fullPage: true })
  await page.evaluate(() => document.documentElement.classList.add("dark"))
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel("Output destination")).toBeVisible()
  await page.screenshot({ path: "test-results/analysis-description-narrow-dark.png", fullPage: true })
  await page.evaluate(() => document.documentElement.classList.remove("dark"))
  await page.setViewportSize({ width: 1600, height: 1050 })
  await page.getByLabel("Output destination").selectOption("clinical_question")
  await expect(page.getByLabel("Section", { exact: true })).toHaveValue("clinical_question")
  await expect(page.getByRole("combobox", { name: "Analysis", exact: true })).toBeDisabled()
  await expect(page.getByRole("combobox", { name: "Evaluate", exact: true })).toBeDisabled()
  await expect(page.getByLabel("Show section heading")).toBeDisabled()
  await page.getByLabel("Conflict group (optional)").fill("clinical_question")
  await expect.poll(() => savedRuleSet.blocks[0].conflict_group).toBe("clinical_question")
  await page.reload()
  await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
  await page.getByText("Section settings", { exact: true }).click()
  await expect(page.getByLabel("Conflict group (optional)")).toHaveValue("clinical_question")
  await expect(page.getByLabel("Match behavior")).toHaveValue("at_most_one")
  await page.screenshot({ path: "test-results/clinical-rule-metadata-desktop.png", fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel("Output destination")).toBeVisible()
  await page.screenshot({ path: "test-results/clinical-rule-metadata-mobile.png", fullPage: true })
})
