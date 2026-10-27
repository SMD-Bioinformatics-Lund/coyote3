import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { RuleSetPreview } from "./RuleSetPreview"
import type { ClinicalRuleSet } from "./clinical-rules-types"
import { sectionStarter } from "./clinical-rule-authoring"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
const scope = { asp_id: "synthetic", diagnosis_id: "base", analyte: "dna" as const, language: "sv", name: "Synthetic" }
const block = sectionStarter([], "closing", scope)
block.rules[0].enabled = true
block.rules[0].output = [{ type: "text", value: "Complete closing sentence." }]
const draft: ClinicalRuleSet = {
  _id: "rules1", revision: 1, scope, blocks: [block], rule_set_id: "synthetic__base__sv",
  schema_version: 1, content_version: 1, name: "Synthetic", status: "draft", active: false,
  analysis_declarations: {}, terminology: {}, test_cases: [], references: [], change_summary: "",
  review: {}, updated_at: "2026-01-01T00:00:00Z", updated_by: "synthetic",
}
function mount(saved = true, canTest = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RuleSetPreview draft={draft} facts={[]} saved={saved} canTest={canTest} /></QueryClientProvider>)
}
describe("Complete rule-set preview", () => {
  it("shows enabled wording for the whole set without pretending to evaluate conditions", () => {
    mount()
    expect(screen.getByText("Complete closing sentence.")).toBeVisible()
    expect(screen.getByText(/Conditional alternatives are labelled/)).toBeVisible()
  })
  it("evaluates authorized sample values using the server after a sample is selected", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [{ id: "sample1", name: "SYNTHETIC", diagnosis_id: "base" }] }, status: 200 })
    vi.mocked(api.post).mockResolvedValue({ data: { summary: "Resolved assay name and all matching sentences.", evaluation: { trace: [{ matched: true }] } }, status: 200 })
    mount(true, true)
    await screen.findByRole("option", { name: "SYNTHETIC · base" })
    fireEvent.change(screen.getByLabelText("Preview sample"), { target: { value: "sample1" } })
    expect(await screen.findByText("Resolved assay name and all matching sentences.")).toBeVisible()
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/clinical-rule-sets/versions/rules1/test-samples/sample1/preview?include_condition_trace=false", undefined, expect.objectContaining({ errorNotice: "inline", signal: expect.anything() })))
  })
  it("waits for unsaved edits instead of displaying an outdated actual result", async () => {
    vi.mocked(api.post).mockClear()
    vi.mocked(api.get).mockResolvedValue({ data: { items: [{ id: "sample1", name: "SYNTHETIC", diagnosis_id: "base" }] }, status: 200 })
    mount(false, true)
    await screen.findByRole("option", { name: "SYNTHETIC · base" })
    fireEvent.change(screen.getByLabelText("Preview sample"), { target: { value: "sample1" } })
    expect(screen.getByRole("status")).toHaveTextContent("Waiting for valid edits")
    expect(api.post).not.toHaveBeenCalled()
  })
})
