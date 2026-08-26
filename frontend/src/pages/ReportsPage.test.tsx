import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), table: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    return <div data-testid="reports-table">{(props.data as unknown[]).length} reports</div>
  },
}))

import { ReportsPage } from "./ReportsPage"

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><ReportsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const payload = {
  reports: [
    {
      oid: "OID_1",
      report_id: "SAMPLE_001_2",
      report_name: "SAMPLE_001_2.html",
      sample_id: "SAMPLE_001",
      asp_id: "hema_gmsv1",
      subpanel_id: "hem",
      environment: "production",
      author: "reviewer",
      time_created: "2026-08-25T10:00:00Z",
      finding_count: 3,
      analysis_counts: { SNV: 2, CNV: 1 },
      has_pdf: true,
    },
  ],
  total: 1,
  page: 1,
  per_page: 50,
  has_next: false,
}

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: payload })
  })

  it("loads the read-only saved report library", async () => {
    mount()

    expect(screen.getByRole("heading", { name: "Saved Reports" })).toBeVisible()
    expect(screen.queryByRole("button", { name: /finalize/i })).not.toBeInTheDocument()
    expect(await screen.findByTestId("reports-table")).toHaveTextContent("1 reports")
    expect(mocks.get).toHaveBeenCalledWith("/reports?page=1&per_page=50")
    expect(mocks.table).toHaveBeenCalledWith(expect.objectContaining({
      data: payload.reports,
      totalCount: 1,
      filename: "saved_reports.csv",
    }))
  })

  it("shows report-library failures", async () => {
    mocks.get.mockRejectedValue(new Error("Reports unavailable"))
    mount()

    expect(await screen.findByText("Reports unavailable")).toBeVisible()
    await waitFor(() => expect(screen.queryByTestId("reports-table")).not.toBeInTheDocument())
  })
})
