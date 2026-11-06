import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { CoverageGeneView } from "./CoverageGeneView"

const mocks = vi.hoisted(() => ({ post: vi.fn(), canManage: true }))
vi.mock("@/lib/api", () => ({ api: { post: mocks.post } }))
vi.mock("@/lib/access-control", async importOriginal => ({
  ...await importOriginal<typeof import("@/lib/access-control")>(),
  useCurrentUserAccess: () => ({ data: {
    username: "synthetic", role: "user", roles: [], access_level: 1,
    permissions: mocks.canManage ? ["coverage.blacklist:manage"] : [],
  } }),
}))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))

beforeEach(() => { vi.clearAllMocks(); mocks.canManage = true })

function mount() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const invalidate = vi.spyOn(client, "invalidateQueries")
  render(<QueryClientProvider client={client}>
    <CoverageGeneView gene="SYNTHETIC" geneData={{ CDS: [{ chr: "1", start: 0, end: 100, cov: 5 }] }} cutoff={20} smpGrp="solid" />
  </QueryClientProvider>)
  return invalidate
}

it("refreshes coverage results after blacklisting a gene", async () => {
  mocks.post.mockResolvedValue({ data: {} })
  const invalidate = mount()
  fireEvent.click(screen.getByRole("button", { name: "Blacklist gene" }))
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["sample-coverage"] }))
})

it("does not offer blacklist mutations without the management permission", () => {
  mocks.canManage = false
  mount()
  expect(screen.queryAllByRole("button", { name: /Blacklist/ })).toHaveLength(0)
})

it("clears inspected measurements when another gene is opened", () => {
  const client = new QueryClient()
  const view = (gene: string) => <QueryClientProvider client={client}>
    <CoverageGeneView gene={gene} geneData={{ CDS: [{ chr: "1", start: 0, end: 100, cov: 5 }] }} cutoff={20} smpGrp="solid" />
  </QueryClientProvider>
  const { rerender } = render(view("FIRST"))
  fireEvent.focus(screen.getByRole("button", { name: "CDS 1, 1:0-100, 5.00X" }))
  expect(screen.queryByText(/Hover over or focus/)).not.toBeInTheDocument()
  rerender(view("SECOND"))
  expect(screen.getByText(/Hover over or focus/)).toBeVisible()
})

it("keeps blacklisted intervals in full context but excludes them from low-exon counts", () => {
  render(<QueryClientProvider client={new QueryClient()}>
    <CoverageGeneView gene="SYNTHETIC" cutoff={20} smpGrp="solid" geneData={{ CDS: [
      { chr: "1", start: 0, end: 100, cov: 5, blacklisted: true },
      { chr: "1", start: 200, end: 300, cov: 10 },
    ] }} />
  </QueryClientProvider>)
  expect(screen.getByRole("button", { name: "Exons (1)" })).toBeVisible()
  expect(screen.getByRole("button", { name: "CDS 1, 1:0-100, 5.00X" })).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: /^CDS \(2\)/i }))
  expect(screen.getByText("Blacklisted")).toBeVisible()
})
