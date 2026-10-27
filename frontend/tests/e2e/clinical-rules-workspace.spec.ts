import { expect, test } from "@playwright/test"

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
  await expect(page.getByRole("heading", { name: "Complete report summary" })).toBeVisible()
  await page.setViewportSize({ width: 1600, height: 1050 })
  await page.screenshot({ path: "test-results/clinical-rule-sentence-desktop.png", fullPage: true })
  await page.getByRole("button", { name: /Revision history/ }).click()
  await expect(page.getByText("draft created")).toBeVisible()
  await expect(page.getByText("First preserved revision")).toBeVisible()
  await page.getByText("Section settings", { exact: true }).click()
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
