import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { installEditLeaseMock, editSessionOptions } from "@/test/edit-lease"

const mocks = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  permissions: ["clinical_rules:draft", "clinical_rules:view"],
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
        permissions: mocks.permissions,
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
  scope: { asp_id: "solid_gmsv3", diagnosis_id: "base", analyte: "dna", language: "sv" },
  name: "Existing solid rules",
  status: "draft",
  active: false,
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
  installEditLeaseMock(mocks.post)
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
    mocks.permissions = ["clinical_rules:draft", "clinical_rules:view"]
    mocks.patch.mockImplementation((_path: string, body: Record<string, unknown>) =>
      Promise.resolve({ data: { ...existingDraft, ...body, revision: 2 } }),
    )
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") {
        return Promise.resolve({
          data: {
            assays: [
              { asp_id: "solid_gmsv3", display_name: "Solid GMSv3", analyte: "dna", diagnoses: [{ diagnosis_id: "base", display_name: "Base" }] },
              { asp_id: "rna_fusion", display_name: "RNA Fusion", analyte: "rna", diagnoses: [{ diagnosis_id: "base", display_name: "Base" }, { diagnosis_id: "solid", display_name: "Solid" }] },
            ],
          },
        })
      }
      return Promise.resolve({ data: { items: [], page: 1, per_page: 30, total: 0 } })
    })
  })

  it.each([
    ["submitted", "clinical_rules:clinical_review", "Start review", "start-clinical-review"],
    ["approved", "clinical_rules:publish", "Publish", "publish"],
    ["in_clinical_review", "clinical_rules:clinical_review", "Approve", "clinical-review"],
    ["in_clinical_review", "clinical_rules:clinical_review", "Reject", "clinical-review"],
  ])("executes the authorized %s transition", async (status, permission, button, action) => {
    mocks.permissions = ["clinical_rules:view", permission]
    const version = { ...existingDraft, status }
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith("/facts")) return Promise.resolve({ data: { items: [] } })
      if (path.endsWith("/authoring-options")) return Promise.resolve({ data: { assays: [], publishers: [{ username: "publisher", name: "Publisher" }] } })
      if (path.endsWith("/versions/rule-version-1")) return Promise.resolve({ data: version })
      return Promise.resolve({ data: { items: [version], total: 1 } })
    })
    mocks.post.mockResolvedValue({ data: version })
    renderPage()
    await userEvent.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    if (button === "Approve") {
      expect(await screen.findByRole("button", { name: button })).toBeDisabled()
      await userEvent.selectOptions(screen.getByLabelText("Assign publisher"), "publisher")
    }
    await userEvent.click(await screen.findByRole("button", { name: button }))
    expect(mocks.post).toHaveBeenCalledWith(
      `/admin/clinical-rule-sets/drafts/rule-version-1/${action}`,
      button === "Approve" ? { approve: true, reason: "Clinical content approved", publisher: "publisher" }
        : button === "Reject" ? { approve: false, reason: "Clinical changes required" }
          : { reason: "Workflow transition" }, {}
    )
  })

  it("selects an installed assay and derives its analyte", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    const assay = screen.getByLabelText("Assay")
    expect(assay).toHaveRole("combobox")
    expect(screen.getByText("Solid GMSv3")).toHaveAttribute("value", "solid_gmsv3")

    fireEvent.change(assay, { target: { value: "rna_fusion" } })
    expect(screen.getByLabelText("Analyte")).toHaveValue("rna")
    expect(screen.getByLabelText("Analyte")).toBeDisabled()
  })

  it("imports a planned assay draft without requiring an installed assay option", async () => {
    const user = userEvent.setup()
    const source = { ...existingDraft, rule_set_id: "planned_hema__base__sv", scope: { ...existingDraft.scope, asp_id: "planned_hema" } }
    mocks.post.mockResolvedValue({ data: source })
    renderPage()
    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    await user.click(screen.getByRole("button", { name: "Import JSON" }))
    await user.upload(screen.getByLabelText("Canonical rule-set JSON"), new File([JSON.stringify(source)], "planned.json", { type: "application/json" }))
    await waitFor(() => expect(screen.getByLabelText("Assay")).toHaveValue("planned_hema"))
    expect(screen.getByLabelText("Analyte")).toBeEnabled()
    expect(screen.getByText(/This assay is not registered yet/)).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Create draft" }))
    expect(mocks.post).toHaveBeenCalledWith("/admin/clinical-rule-sets/imports", expect.objectContaining({ scope: source.scope, document: source }), {})
  })

  it("links the existing draft through a revision-qualified scope edit", async () => {
    const user = userEvent.setup()
    const fallback = mocks.get.getMockImplementation()!
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith("/versions/rule-version-1")) return Promise.resolve({ data: existingDraft })
      if (path === "/admin/clinical-rule-sets?q=") return Promise.resolve({ data: { items: [existingDraft] } })
      return fallback(path)
    })
    renderPage()
    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await waitFor(() => expect(screen.getByLabelText("Rule-set name")).toBeEnabled())
    await user.click(screen.getByText(/Assay association:/))
    const assay = screen.getByLabelText("Link to assay")
    expect(within(assay).queryByRole("option", { name: /RNA Fusion/ })).not.toBeInTheDocument()
    await user.selectOptions(assay, "solid_gmsv3")
    await user.click(screen.getByRole("button", { name: "Link assay" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith(
      "/admin/clinical-rule-sets/drafts/rule-version-1", expect.objectContaining({ revision: 1, scope: existingDraft.scope }), editSessionOptions,
    ))
  })

  it("pauses a failed autosave instead of submitting the same edit repeatedly", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith("/facts")) return Promise.resolve({ data: { items: [] } })
      if (path.endsWith("/authoring-options")) return Promise.resolve({ data: { assays: [] } })
      if (path.endsWith("/versions/rule-version-1")) return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], total: 1 } })
    })
    mocks.patch.mockRejectedValue(new Error("Validation failed"))
    renderPage()
    await userEvent.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await waitFor(() => expect(screen.getByLabelText("Rule-set name")).toBeEnabled())
    vi.useFakeTimers()
    try {
      fireEvent.change(screen.getByLabelText("Rule-set name"), { target: { value: "Changed draft" } })
      await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
      expect(mocks.patch).toHaveBeenCalledTimes(1)
      expect(screen.getByText(/Autosave paused/)).toBeVisible()
      await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
      expect(mocks.patch).toHaveBeenCalledTimes(1)
      expect(screen.getByRole("button", { name: "Retry save" })).toBeEnabled()
    } finally { vi.useRealTimers() }
  })

  it("offers JSON import beside export for an existing rule set", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith("/facts")) return Promise.resolve({ data: { items: [] } })
      if (path.endsWith("/authoring-options")) return Promise.resolve({ data: { assays: [] } })
      if (path.endsWith("/versions/rule-version-1")) return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], total: 1 } })
    })
    renderPage()
    await userEvent.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    expect(await screen.findByRole("button", { name: "Export JSON" })).toBeVisible()
    await userEvent.click(screen.getByRole("button", { name: "Import JSON" }))
    expect(screen.getByRole("region", { name: "Create clinical rule set" })).toBeVisible()
    expect(screen.getByText("Canonical rule-set JSON")).toBeVisible()
  })

  it("saves automatic annotation wording with the governed draft", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith("/facts")) return Promise.resolve({ data: { items: [] } })
      if (path.endsWith("/authoring-options")) return Promise.resolve({ data: { assays: [] } })
      if (path.endsWith("/versions/rule-version-1")) return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], total: 1 } })
    })
    renderPage()
    await userEvent.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await waitFor(() => expect(screen.getByLabelText("Tumor-type wording")).toBeEnabled())
    fireEvent.change(screen.getByLabelText("Tumor-type wording"), { target: { value: "solida" } })
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith(
      "/admin/clinical-rule-sets/drafts/rule-version-1",
      expect.objectContaining({ terminology: { automatic_annotation_tumor_type: "solida" } }), editSessionOptions
    ))
  })

  it("generates an editable rule-set name from the assay and diagnosis", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "New rule set" }))
    fireEvent.change(screen.getByLabelText("Assay"), { target: { value: "rna_fusion" } })
    expect(screen.getByLabelText("Rule-set name")).toHaveValue("RNA Fusion clinical report rules")

    await user.selectOptions(screen.getByLabelText("Diagnosis"), "solid")
    expect(screen.getByLabelText("Rule-set name")).toHaveValue(
      "RNA Fusion - solid clinical report rules",
    )

    await user.clear(screen.getByLabelText("Rule-set name"))
    await user.type(screen.getByLabelText("Rule-set name"), "Custom RNA wording")
    await user.selectOptions(screen.getByLabelText("Diagnosis"), "base")
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

  it("adds named sections, enables the analysis and reorders without losing rules", async () => {
    const user = userEvent.setup()
    mocks.get.mockImplementation((path: string) => {
      if (path === "/admin/clinical-rule-sets/facts") return Promise.resolve({ data: { items: [] } })
      if (path === "/admin/clinical-rule-sets/authoring-options") return Promise.resolve({ data: { assays: [] } })
      if (path === "/admin/clinical-rule-sets/versions/rule-version-1") return Promise.resolve({ data: existingDraft })
      return Promise.resolve({ data: { items: [existingDraft], page: 1, per_page: 30, total: 1 } })
    })
    renderPage()
    await user.click(await screen.findByRole("button", { name: /Existing solid rules/ }))
    await user.selectOptions(await screen.findByLabelText("Section starter"), "intro")
    expect(screen.getByLabelText("Section")).toHaveValue("General introduction")
    expect(screen.getByLabelText("Show section heading")).not.toBeChecked()
    expect(screen.getByLabelText("Include this rule in generated report text")).not.toBeChecked()
    await user.selectOptions(screen.getByLabelText("Section starter"), "cnv")
    expect(screen.getByLabelText("Analysis")).toHaveValue("CNV")
    const identifier = (screen.getByLabelText("Section identifier") as HTMLInputElement).value
    await user.click(screen.getByRole("button", { name: "Move section up" }))
    expect(screen.getByLabelText("Section identifier")).toHaveValue(identifier)
    expect(screen.getByLabelText("Clinical rule name")).toHaveValue("CNV text")
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
    await user.click(screen.getByText("Section settings", { exact: true }))
    await user.click(screen.getByText("Rule details and identifier", { exact: true }))
    expect(screen.getByLabelText("Rule identifier")).toHaveValue("report_section_1_rule_1")
    expect(screen.getByLabelText("Match behavior")).toHaveValue("at_most_one")
    await user.selectOptions(screen.getByLabelText("Match behavior"), "first_match")
    await user.type(screen.getByLabelText("Conflict group (optional)"), "classification")
    expect(screen.getByLabelText("Match behavior")).toHaveValue("at_most_one")
    expect(screen.getByRole("option", { name: "First match" })).toBeDisabled()

    await user.clear(screen.getByLabelText("Rule identifier"))
    await user.type(screen.getByLabelText("Rule identifier"), "custom_result_rule")
    expect(screen.getByLabelText("Rule identifier")).toHaveValue("custom_result_rule")

    await user.selectOptions(screen.getByLabelText("Output destination"), "clinical_question")
    expect(screen.getByLabelText("Section")).toHaveValue("clinical_question")
    expect(screen.getByLabelText("Section")).toBeDisabled()
    expect(screen.getByLabelText("Evaluate")).toHaveValue("once")
    expect(screen.getByLabelText("Analysis")).toHaveValue("")
    expect(screen.getByLabelText("Show section heading")).not.toBeChecked()
    expect(screen.getByLabelText("Match behavior")).toHaveValue("at_most_one")
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
    const confirmation = screen.getByRole("alertdialog", { name: "Delete unpublished version?" })
    expect(confirmation).toBeVisible()
    await user.click(within(confirmation).getByRole("button", { name: "Delete version" }))

    expect(mocks.delete).toHaveBeenCalledWith(
      "/admin/clinical-rule-sets/drafts/rule-version-1?revision=1", editSessionOptions
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
    fireEvent.change(screen.getByLabelText("Assay"), { target: { value: "solid_gmsv3" } })
    await user.click(screen.getByRole("button", { name: "Create draft" }))

    expect(await screen.findByLabelText("Clinical rule name")).toHaveValue("Report section 1 rule 1")
    expect(screen.getByRole("button", { name: "Add condition" })).toBeVisible()
    expect(screen.getByText("2. Report text")).toBeVisible()
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
