import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
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
function mount(saved = true, canTest = false, document = draft) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RuleSetPreview draft={document} facts={[]} saved={saved} canTest={canTest} /></QueryClientProvider>)
}
describe("Complete rule-set preview", () => {
  it("shows enabled wording for the whole set without pretending to evaluate conditions", () => {
    mount()
    expect(screen.getByText("Complete closing sentence.")).toBeVisible()
    expect(screen.getByText(/Conditional sentences are shown separately/)).toBeVisible()
  })

  it("separates conditional continuations into named cards in report order", () => {
    const document = structuredClone(draft)
    const first = document.blocks[0].rules[0]
    document.blocks[0].show_heading = false
    document.blocks[0].match_strategy = "first_match"
    document.blocks[0].rules = [
      { ...first, rule_id: "unpaired", name: "Unpaired wording", order: 3, presentation: "continue", condition: { type: "predicate", fact: "sample.paired", operator: "eq", value: false }, output: [{ type: "text", value: "No paired control was used." }] },
      { ...first, rule_id: "hidden", name: "Disabled alternative", order: 0, enabled: false },
      { ...first, rule_id: "paired", name: "Paired wording", order: 2, presentation: "continue", condition: { type: "predicate", fact: "sample.paired", operator: "eq", value: true }, output: [{ type: "text", value: "A paired control was used." }] },
      { ...first, order: 1 },
    ]
    mount(true, false, document)
    const cards = screen.getAllByRole("article")
    expect(cards).toHaveLength(3)
    expect(within(cards[0]).getByText("Complete closing sentence.")).toBeVisible()
    expect(cards[1]).toHaveAccessibleName("Paired wording")
    expect(within(cards[1]).getByText("A paired control was used.")).toBeVisible()
    expect(within(cards[1]).queryByText("No paired control was used.")).not.toBeInTheDocument()
    expect(cards[2]).toHaveAccessibleName("Unpaired wording")
    expect(screen.queryByText("Disabled alternative")).not.toBeInTheDocument()
    expect(screen.getAllByText(/Continue previous sentence/)).toHaveLength(2)
    expect(screen.getByText("Use the first matching sentence only.")).toBeVisible()
    expect(screen.getByText(/No heading in report/)).toBeVisible()
    fireEvent.click(within(cards[1]).getByText("When this sentence applies"))
    expect(within(cards[1]).getByText("sample.paired is Yes")).toBeVisible()
    fireEvent.click(screen.getByLabelText("Show conditional wording"))
    expect(screen.queryByText("A paired control was used.")).not.toBeInTheDocument()
    expect(screen.queryByText("No paired control was used.")).not.toBeInTheDocument()
    expect(screen.getByText("Complete closing sentence.")).toBeVisible()
    expect(screen.getByRole("article", { name: "Paired wording" })).toBeVisible()
  })
  it("evaluates authorized sample values using the server after a sample is selected", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [{ id: "sample1", name: "SYNTHETIC", diagnosis_id: "base" }] }, status: 200 })
    vi.mocked(api.post).mockResolvedValue({ data: { summary: "Resolved assay name and all matching sentences.", evaluation: { trace: [{ matched: true }] } }, status: 200 })
    mount(true, true)
    await screen.findByRole("option", { name: "SYNTHETIC · base" })
    fireEvent.change(screen.getByLabelText("Preview sample"), { target: { value: "sample1" } })
    expect(await screen.findByText("Resolved assay name and all matching sentences.")).toBeVisible()
    expect(screen.queryByText("Report structure")).not.toBeInTheDocument()
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
