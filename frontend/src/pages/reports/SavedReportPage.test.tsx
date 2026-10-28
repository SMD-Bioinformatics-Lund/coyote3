import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen } from "@testing-library/react"
import { Link, MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), getBlob: vi.fn(), table: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get, getBlob: mocks.getBlob } }))
vi.mock("@/lib/runtime-paths", () => ({
  apiPath: (path: string) => `/coyote3/api/v1${path}`,
}))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    return <div data-testid="findings-table">{(props.data as unknown[]).length} findings</div>
  },
}))
vi.mock("@/components/reports/ReportHtmlFrame", () => ({
  ReportHtmlFrame: ({ title, html }: { title: string; html: string }) => <div title={title}>{html}</div>,
}))

import { SavedReportPage } from "./SavedReportPage"

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/samples/SAMPLE_001/reports/REPORT_7"]}>
        <Link to="/samples/SAMPLE_002/reports/REPORT_8">Next report</Link>
        <Routes>
          <Route path="/samples/:id/reports/:reportId" element={<SavedReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const context = {
  sample_id: "SAMPLE_001",
  report_id: "REPORT_7",
  report_name: "REPORT_7.html",
  asp_id: "hema_gmsv1",
  diagnosis_id: "hem",
  environment: "production",
  author: "reviewer",
  time_created: "2026-08-25T10:00:00Z",
  finding_count: 2,
  analysis_counts: { SNV: 1, CNV: 1 },
  findings: [
    { analysis_type: "SNV", gene: "TP53", hgvsp: "p.Arg175His", tier: 1 },
    { analysis_type: "CNV", genes: ["MYC"], cnv: "8q gain", tier: 2 },
  ],
}

describe("SavedReportPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: context })
    mocks.getBlob.mockResolvedValue({ data: new Blob(["<main>Clinical report</main>"]) })
  })

  it("shows saved HTML and its immutable reported findings", async () => {
    mount()

    expect(screen.getByRole("status", { name: "Loading saved report" })).toBeVisible()
    expect(await screen.findByTitle("SAMPLE_001 saved report")).toHaveTextContent("Clinical report")
    expect(screen.getByTestId("findings-table")).toHaveTextContent("2 findings")
    expect(mocks.get).toHaveBeenCalledWith("/samples/SAMPLE_001/reports/REPORT_7/context", expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(mocks.table).toHaveBeenCalledWith(expect.objectContaining({ data: context.findings }))
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
      "href",
      "/coyote3/api/v1/samples/SAMPLE_001/reports/REPORT_7/download",
    )
    expect(screen.getByRole("link", { name: "All reports" })).toHaveAttribute("href", "/reports")
  })

  it("shows the saved HTML retrieval error", async () => {
    mocks.getBlob.mockRejectedValue(new Error("Report was retired"))
    mount()

    expect(await screen.findByText("Report was retired")).toBeVisible()
  })

  it("shows finding-context failures", async () => {
    mocks.get.mockRejectedValue(new Error("Finding snapshot unavailable"))
    mount()

    expect(await screen.findByText("Finding snapshot unavailable")).toBeVisible()
  })

  it("removes the previous document immediately on navigation and aborts an abandoned load", async () => {
    let pendingSignal: AbortSignal | undefined
    mocks.getBlob.mockResolvedValueOnce({ data: new Blob(["First saved report"]) })
      .mockImplementationOnce((_path: string, options: { signal: AbortSignal }) => {
        pendingSignal = options.signal
        return new Promise(() => undefined)
      })
    const view = mount()
    expect(await screen.findByTitle("SAMPLE_001 saved report")).toHaveTextContent("First saved report")
    fireEvent.click(screen.getByRole("link", { name: "Next report" }))
    expect(screen.queryByText("First saved report")).not.toBeInTheDocument()
    expect(screen.getByRole("status", { name: "Loading saved report" })).toBeVisible()
    expect(pendingSignal?.aborted).toBe(false)
    view.unmount()
    expect(pendingSignal?.aborted).toBe(true)
  })
})
