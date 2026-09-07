import { expect, test } from "@playwright/test"

import { installApiFixtures } from "./support/api-fixtures"

const ruleSet = {
  _id: "rule-version-1",
  rule_set_id: "assay_1__base__sv",
  schema_version: 1,
  content_version: 1,
  revision: 1,
  scope: { asp_id: "assay_1", subpanel_id: "base", analyte: "dna", language: "sv" },
  name: "Assay 1 report rules",
  status: "draft",
  active: false,
  minimum_engine_version: 1,
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
    match_strategy: "first_match",
    rules: [{ rule_id: "summary", name: "Summary", order: 10, enabled: true, condition: null, output: [{ type: "text", value: "No reportable findings." }], references: [] }],
  }],
  test_cases: [],
  references: [],
  change_summary: "",
  review: {},
  updated_at: "2026-09-05T12:00:00Z",
  updated_by: "admin",
}

test("clinical rule panes fill the workspace and reflow into selectable rails", async ({ page }) => {
  await installApiFixtures(page, (path) => {
    if (path === "/api/v1/auth/whoami") return { json: { username: "admin", role: "admin", roles: ["admin"], access_level: 99_999, permissions: ["clinical_rules:view", "clinical_rules:draft", "clinical_rules:test"] } }
    if (path === "/api/v1/admin/clinical-rule-sets/facts") return { json: { items: [] } }
    if (path === "/api/v1/admin/clinical-rule-sets/authoring-options") return { json: { assays: [{ asp_id: "assay_1", display_name: "Assay 1", analyte: "dna" }] } }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1") return { json: ruleSet }
    if (path === "/api/v1/admin/clinical-rule-sets/versions/rule-version-1/revisions") return { json: { items: [{ rule_set_oid: ruleSet._id, rule_set_id: ruleSet.rule_set_id, content_version: 1, revision: 1, action: "draft_created", actor: "admin", occurred_at: "2026-09-05T12:00:00Z", revision_hash: "a".repeat(64), document: ruleSet }] } }
    if (path === "/api/v1/admin/clinical-rule-sets") return { json: { items: [ruleSet], page: 1, per_page: 30, total: 1 } }
  })

  await page.goto("/admin/clinical-rules")
  await page.getByRole("button", { name: /Assay 1 report rules/ }).click()
  await expect(page.locator("aside").getByText("No reportable findings.")).toBeVisible()

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
  await expect(page.getByRole("heading", { name: "Live text preview" })).toBeVisible()
  await page.getByRole("button", { name: /Revision history/ }).click()
  await expect(page.getByText("draft created")).toBeVisible()
  await expect(page.getByText("First preserved revision")).toBeVisible()
})
