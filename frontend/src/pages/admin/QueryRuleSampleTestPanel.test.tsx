import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { QueryRuleSampleTestPanel } from "./QueryRuleSampleTestPanel"

vi.mock("@/lib/api", () => ({ api: { post: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn() }))
beforeEach(() => vi.resetAllMocks())
const scope = { assay_group: "group", asp_id: null, subpanel_id: null, analysis: "snv", intent: "somatic" }
const sample = { id: "synthetic", name: "SYNTHETIC", asp_id: "example", subpanel_id: "base" }

it("searches on request, compares a sample, and hides results when the draft changes", async () => {
  vi.mocked(api.post).mockResolvedValueOnce({ status: 200, data: { items: [sample], total: 1, page: 1, per_page: 20 } })
    .mockResolvedValueOnce({ status: 200, data: { sample, published_count: 2, draft_count: 1, added_count: 0, removed_count: 1, unchanged_count: 1,
      added: [], removed: [{ id: "finding", label: "Removed variant" }], display_limit: 100, persisted: false, draft_policy: { lineage: [] }, published_query: { SAMPLE_ID: "synthetic" }, draft_query: { SAMPLE_ID: "synthetic", CHROM: "1" }, post_filters: [] } })
  const client = new QueryClient()
  const tree = (content: unknown) => <QueryClientProvider client={client}><QueryRuleSampleTestPanel scope={scope} content={content} /></QueryClientProvider>
  const mounted = render(tree({ exceptions: [] }))
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Find samples" }))
  fireEvent.click(await screen.findByRole("button", { name: "Test SYNTHETIC" }))
  await screen.findByText("Removed variant")
  expect(screen.getByRole("region", { name: "Final MongoDB queries" })).toHaveTextContent('"CHROM": "1"')
  expect(api.post).toHaveBeenLastCalledWith("/admin/query-rule-sets/test-samples/synthetic/preview", { scope, content: { exceptions: [] } })
  mounted.rerender(tree({ exceptions: null }))
  expect(screen.queryByText("Removed variant")).not.toBeInTheDocument()
  expect(screen.queryByRole("region", { name: "Final MongoDB queries" })).not.toBeInTheDocument()
})

it("does not retain search results from a different scope", async () => {
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: { items: [sample], total: 1, page: 1, per_page: 20 } })
  const client = new QueryClient()
  const tree = (analysis: string) => <QueryClientProvider client={client}><QueryRuleSampleTestPanel scope={{ ...scope, analysis }} content={{}} /></QueryClientProvider>
  const mounted = render(tree("snv"))
  fireEvent.click(screen.getByRole("button", { name: "Find samples" }))
  await screen.findByRole("button", { name: "Test SYNTHETIC" })
  mounted.rerender(tree("cnv"))
  expect(screen.queryByRole("button", { name: "Test SYNTHETIC" })).not.toBeInTheDocument()
})
