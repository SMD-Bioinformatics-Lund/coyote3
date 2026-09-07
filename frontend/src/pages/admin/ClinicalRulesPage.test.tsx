import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api: { delete: mocks.delete, get: mocks.get, post: mocks.post, patch: mocks.patch },
}))

vi.mock("@/lib/access-control", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/access-control")>()
  return {
    ...actual,
    useCurrentUserAccess: () => ({
      data: {
        username: "admin",
        roles: ["admin"],
        role: "admin",
        permissions: ["clinical_rules:draft", "clinical_rules:view"],
      },
      isLoading: false,
    }),
  }
})

import { ClinicalRulesPage } from "./ClinicalRulesPage"

const existingDraft = {
  _id: "rule-version-1",
  rule_set_id: "solid_gmsv3__base__sv",
  schema_version: 1,
  content_version: 1,
  revision: 1,
  scope: { asp_id: "solid_gmsv3", subpanel_id: "base", analyte: "dna", language: "sv" },
  name: "Existing solid rules",
  status: "draft",
  active: false,
  minimum_engine_version: 1,
  analysis_declarations: {},
  terminology: {},
  blocks: [],
  test_cases: [],
  references: [],
  change_summary: "",
  review: {},
  updated_at: "2026-09-05T12:00:00Z",
  updated_by: "admin",
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ClinicalRulesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("ClinicalRulesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.patch.mockImplementation((_path: string, body: Record<string, unknown>) =>
      Promise.resolve({ data: { ...existingDraft, ...body, revision: 2 } }),
    )
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") {
        return Promise.resolve({
          data: {
            assays: [
              { asp_id: "solid_gmsv3", display_name: "Solid GMSv3", analyte: "dna" },
              { asp_id: "rna_fusion", display_name: "RNA Fusion", analyte: "rna" },
            ],
          },
        })
      }
      return Promise.resolve({ data: { items: [], page: 1, per_page: 30, total: 0 } })
    })
  })

  it("selects an installed assay and derives its analyte", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    const assay = screen.getByLabelText("Assay")
    expect(assay).toHaveRole("combobox")
    expect(screen.getByRole("option", { name: "Solid GMSv3 (solid_gmsv3)" })).toBeVisible()

    await user.selectOptions(assay, "rna_fusion")
    expect(screen.getByLabelText("Analyte")).toHaveValue("rna")
    expect(screen.getByLabelText("Analyte")).toHaveAttribute("readonly")
  })

  it("generates an editable rule-set name from the assay and subpanel", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    await user.selectOptions(screen.getByLabelText("Assay"), "rna_fusion")
    expect(screen.getByLabelText("Rule-set name")).toHaveValue("RNA Fusion clinical report rules")

    await user.clear(screen.getByLabelText("Subpanel"))
    await user.type(screen.getByLabelText("Subpanel"), "solid")
    expect(screen.getByLabelText("Rule-set name")).toHaveValue(
      "RNA Fusion - solid clinical report rules",
    )

    await user.clear(screen.getByLabelText("Rule-set name"))
    await user.type(screen.getByLabelText("Rule-set name"), "Custom RNA wording")
    await user.clear(screen.getByLabelText("Subpanel"))
    await user.type(screen.getByLabelText("Subpanel"), "base")
    expect(screen.getByLabelText("Rule-set name")).toHaveValue("Custom RNA wording")
  })

  it("clears an open rule set when starting a new one", async () => {
    const user = userEvent.setup()
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") {
        return Promise.resolve({
          data: { assays: [{ asp_id: "solid_gmsv3", display_name: "Solid GMSv3", analyte: "dna" }] },
        })
      }
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") {
        return Promise.resolve({ data: existingDraft })
      }
      return Promise.resolve({
        data: { items: [existingDraft], page: 1, per_page: 30, total: 1 },
      })
    })
    renderPage()

    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    expect(await screen.findByRole("textbox", { name: "Rule-set name" })).toHaveValue(
      "Existing solid rules",
    )

    await user.click(screen.getByRole("button", { name: "New rule set" }))
    expect(screen.getByRole("region", { name: "Create clinical rule set" })).toBeVisible()
    expect(screen.getByText("Select a rule set to inspect or edit.")).toBeVisible()
    expect(screen.queryByDisplayValue("Existing solid rules")).not.toBeInTheDocument()
  })

  it("keeps the selected rule set open when its sidebar row is clicked again", async () => {
    const user = userEvent.setup()
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], page: 1, per_page: 30, total: 1 } })
    })
    renderPage()

    const ruleSet = await screen.findByRole("button", { name: /Existing solid rules/ })
    await user.click(ruleSet)
    expect(await screen.findByRole("textbox", { name: "Rule-set name" })).toHaveValue("Existing solid rules")

    await user.click(ruleSet)
    expect(screen.getByRole("textbox", { name: "Rule-set name" })).toHaveValue("Existing solid rules")
  })

  it("generates editable section and clinical rule identifiers", async () => {
    const user = userEvent.setup()
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") {
        return Promise.resolve({ data: existingDraft })
      }
      return Promise.resolve({
        data: { items: [existingDraft], page: 1, per_page: 30, total: 1 },
      })
    })
    renderPage()

    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await user.click(await screen.findByRole("button", { name: "Add section" }))

    expect(screen.getByLabelText("Section")).toHaveValue("Report section 1")
    expect(screen.getByLabelText("Section identifier")).toHaveValue("report_section_1")
    expect(screen.getByLabelText("Clinical rule name")).toHaveValue("Report section 1 rule 1")
    expect(screen.getByLabelText("Rule identifier")).toHaveValue("report_section_1_rule_1")

    await user.clear(screen.getByLabelText("Rule identifier"))
    await user.type(screen.getByLabelText("Rule identifier"), "custom_result_rule")
    expect(screen.getByLabelText("Rule identifier")).toHaveValue("custom_result_rule")
  })

  it("deletes only the selected draft after confirmation", async () => {
    const user = userEvent.setup()
    mocks.delete.mockResolvedValue({ data: {}, status: 204 })
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], page: 1, per_page: 30, total: 1 } })
    })
    renderPage()

    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await user.click(await screen.findByRole("button", { name: "Delete draft" }))
    const confirmation = screen.getByRole("alertdialog", { name: "Delete draft?" })
    expect(confirmation).toBeVisible()
    await user.click(within(confirmation).getByRole("button", { name: "Delete draft" }))

    expect(mocks.delete).toHaveBeenCalledWith(
      "/admin/clinical-rule-sets/drafts/rule-version-1?revision=1",
    )
    expect(await screen.findByText("Select a rule set to inspect or edit.")).toBeVisible()
  })

  it("opens a newly created draft directly in the visual rule builder", async () => {
    const user = userEvent.setup()
    const newDraft = {
      ...existingDraft,
      _id: "new-rule-version",
      name: "New rule set",
      blocks: [{
        block_id: "report_section_1",
        name: "Report section 1",
        analysis: null,
        evaluation: { mode: "once", collection: null },
        section: "Report section 1",
        section_order: 100,
        block_order: 10,
        show_heading: true,
        match_strategy: "first_match",
        rules: [{
          rule_id: "report_section_1_rule_1",
          name: "Report section 1 rule 1",
          order: 10,
          enabled: false,
          condition: null,
          output: [{ type: "text", value: "Add report wording." }],
          references: [],
        }],
      }],
    }
    mocks.post.mockResolvedValue({ data: newDraft })
    renderPage()

    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    await user.selectOptions(screen.getByLabelText("Assay"), "solid_gmsv3")
    await user.click(screen.getByRole("button", { name: "Create draft" }))

    expect(await screen.findByLabelText("Clinical rule name")).toHaveValue("Report section 1 rule 1")
    expect(screen.getByRole("button", { name: "Add condition" })).toBeVisible()
    expect(screen.getByText("Report text")).toBeVisible()
    expect(screen.getByLabelText("Include this rule in generated report text")).not.toBeChecked()
  })

  it("collapses the rule-set and section sidebars into vertical rails", async () => {
    const user = userEvent.setup()
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], page: 1, per_page: 30, total: 1 } })
    })
    renderPage()

    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await user.click(await screen.findByRole("button", { name: "Add section" }))
    expect(screen.getByRole("separator", { name: "Resize rule-set list" })).toBeVisible()
    expect(screen.getByRole("separator", { name: "Resize report sections" })).toBeVisible()
    expect(screen.getByRole("separator", { name: "Resize text preview" })).toBeVisible()

    const ruleSetDivider = screen.getByRole("separator", { name: "Resize rule-set list" })
    const initialWidth = Number(ruleSetDivider.getAttribute("aria-valuenow"))
    fireEvent.keyDown(ruleSetDivider, { key: "ArrowRight" })
    expect(ruleSetDivider).toHaveAttribute("aria-valuenow", String(initialWidth + 16))

    await user.click(screen.getByTitle("Collapse rule-set list"))
    expect(screen.getByRole("button", { name: "Expand rule-set list" })).toBeVisible()
    expect(screen.queryByRole("separator", { name: "Resize rule-set list" })).not.toBeInTheDocument()

    await user.click(screen.getByTitle("Collapse report sections"))
    expect(screen.getByRole("button", { name: "Expand report sections" })).toBeVisible()
    expect(screen.getByRole("button", { name: "Select section Report section 1" })).toBeVisible()
    expect(screen.queryByRole("separator", { name: "Resize report sections" })).not.toBeInTheDocument()
  })

  it("shows an immutable revision snapshot on demand", async () => {
    const user = userEvent.setup()
    const preserved = {
      rule_set_oid: existingDraft._id,
      rule_set_id: existingDraft.rule_set_id,
      content_version: 1,
      revision: 1,
      action: "draft_created",
      actor: "clinical.author",
      occurred_at: "2026-09-05T12:00:00Z",
      reason: "Initial wording",
      revision_hash: "a".repeat(64),
      document: existingDraft,
    }
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") return Promise.resolve({ data: existingDraft })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1/revisions") return Promise.resolve({ data: { items: [preserved] } })
      return Promise.resolve({ data: { items: [existingDraft], page: 1, per_page: 30, total: 1 } })
    })
    renderPage()

    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await user.click(await screen.findByRole("button", { name: /Revision history/ }))

    expect(await screen.findByText("draft created")).toBeVisible()
    expect(screen.getByText("clinical.author")).toBeVisible()
    expect(screen.getByText("Initial wording")).toBeVisible()
    expect(screen.getByText("First preserved revision")).toBeVisible()
  })
})
