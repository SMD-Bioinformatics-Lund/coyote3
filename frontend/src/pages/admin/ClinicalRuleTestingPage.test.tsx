import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock("@/lib/api", () => ({ api: mocks }))

import { ClinicalRuleTestingPage } from "./ClinicalRuleTestingPage"

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ClinicalRuleTestingPage /></QueryClientProvider>)
}

describe("ClinicalRuleTestingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockImplementation((path: string) => {
      if (path.includes("test-samples")) {
        return Promise.resolve({ data: { items: [{ id: "sample-1", name: "Sample 1", asp_id: "assay_1", subpanel_id: "base", environment: "production", omics_layer: "dna" }] } })
      }
      return Promise.resolve({ data: { items: [{ _id: "rule-1", name: "Assay rules", content_version: 2, status: "draft", scope: { asp_id: "assay_1", subpanel_id: "base", analyte: "dna" } }] } })
    })
    mocks.post.mockResolvedValue({ data: { sample: { id: "sample-1", name: "Sample 1", subpanel_id: "base" }, rule_set: { rule_set_id: "assay_1__base__sv", content_version: 2, status: "draft" }, summary: "## Result\n\nNo reportable findings.", evaluation: { sections: { Result: ["No reportable findings."] }, trace: [{ block_id: "result", rule_id: "negative", section: "Result", matched: true, missing_facts: [], condition_trace: { type: "all", label: "Match all", matched: true, missing_facts: [], children: [{ type: "predicate", label: "Finding count eq 0", matched: true, missing_facts: [], children: [] }] } }] }, persisted: false } })
  })

  it("tests a selected rule version against a compatible sample as a read-only preview", async () => {
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole("option", { name: /Assay rules/ })
    await user.selectOptions(screen.getByLabelText("Rule set"), "rule-1")
    await user.click(await screen.findByRole("button", { name: /Sample 1/ }))
    await user.click(screen.getByRole("button", { name: "Test rule set" }))

    expect(await screen.findByText("No reportable findings.")).toBeVisible()
    expect(screen.getByText("No data was persisted.", { exact: false })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Show execution trace" }))
    expect(screen.getByText("Condition passed")).toBeVisible()
    expect(screen.getByText("Finding count eq 0")).toBeVisible()
    expect(mocks.post).toHaveBeenNthCalledWith(
      1,
      "/admin/clinical-rule-sets/versions/rule-1/test-samples/sample-1/preview?include_condition_trace=false",
    )
    expect(mocks.post).toHaveBeenNthCalledWith(
      2,
      "/admin/clinical-rule-sets/versions/rule-1/test-samples/sample-1/preview?include_condition_trace=true",
    )
    expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining("per_page=10"))
  })
})
