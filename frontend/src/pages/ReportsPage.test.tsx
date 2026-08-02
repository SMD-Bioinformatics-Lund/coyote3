import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), table: vi.fn(), success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: mocks.success, notifyActionError: mocks.error }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    return <div data-testid="snapshot-table">{(props.data as unknown[]).length} rows</div>
  },
}))
vi.mock("@/components/reports/ReportHtmlFrame", () => ({
  ReportHtmlFrame: ({ title, html }: { title: string; html: string }) => <div data-testid="report-frame" data-title={title}>{html}</div>,
}))

import { ReportsPage } from "./ReportsPage"

function mount(route = "/reports") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}><ReportsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const preview = {
  sample: { name: "SAMPLE_001", asp_id: "hema_gmsv1", subpanel_id: "hem" },
  meta: { template_status: { status: "ready", has_html: true, message: "Ready" } },
  report: { html: "<h1>Rendered report</h1>", snapshot_rows: [{ gene: "TP53", tier: 1 }] },
}

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith("/samples?")) return Promise.resolve({ data: { live_samples: [] } })
      return Promise.resolve({ data: preview })
    })
    mocks.post.mockResolvedValue({ data: { report: { id: "REPORT_9" } } })
  })

  it("does not request a preview before a sample is selected", () => {
    mount()

    expect(screen.getByRole("heading", { name: "Report Workspace" })).toBeVisible()
    expect(mocks.get).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Refresh Preview" })).toBeDisabled()
  })

  it("looks up samples and selects an autocomplete result", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith("/samples?")) {
        return Promise.resolve({ data: { live_samples: [{ _id: "OID_1", name: "SAMPLE_001", asp_id: "hema_gmsv1", subpanel_id: "hem" }] } })
      }
      return Promise.resolve({ data: preview })
    })
    const user = userEvent.setup()
    mount()

    await user.type(screen.getByPlaceholderText(/Search sample name/), "SAMPLE")
    const result = await screen.findByRole("button", { name: /SAMPLE_001/ })
    await user.click(result)

    expect(await screen.findByTestId("report-frame")).toHaveTextContent("Rendered report")
    expect(mocks.get).toHaveBeenCalledWith("/samples/SAMPLE_001/reports/dna/preview?include_snapshot=true")
  })

  it("hydrates URL state, renders a snapshot, switches type, and finalizes", async () => {
    const user = userEvent.setup()
    mount("/reports?sample_id=SAMPLE_001&report_type=dna")

    expect(await screen.findByText("template ready")).toBeVisible()
    expect(screen.getByTestId("snapshot-table")).toHaveTextContent("1 rows")
    expect(mocks.table).toHaveBeenCalledWith(expect.objectContaining({
      data: preview.report.snapshot_rows,
      filename: "SAMPLE_001_dna_snapshot.csv",
    }))

    await user.selectOptions(screen.getByLabelText("Report type"), "rna")
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith("/samples/SAMPLE_001/reports/rna/preview?include_snapshot=true"))

    await user.click(screen.getByRole("button", { name: "Finalize" }))
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/samples/SAMPLE_001/reports/rna", {
      html: preview.report.html,
      snapshot_rows: preview.report.snapshot_rows,
    }))
    expect(await screen.findByText("Report saved: REPORT_9")).toBeVisible()
    expect(mocks.success).toHaveBeenCalledWith("Report saved", "Report REPORT_9 was saved.", "Reports")
  })

  it("disables finalization and explains an unavailable template", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith("/samples?")) return Promise.resolve({ data: { live_samples: [] } })
      return Promise.resolve({ data: {
        sample: { name: "SAMPLE_001" },
        meta: { template_status: { status: "missing", has_html: false, message: "No approved rule source" } },
        report: { html: "", snapshot_rows: [] },
      } })
    })
    mount("/reports?sample_id=SAMPLE_001")

    expect(await screen.findByText("No approved rule source")).toBeVisible()
    expect(screen.getByText("No rendered report HTML was returned for this preview.")).toBeVisible()
    expect(screen.getByRole("button", { name: "Finalize" })).toBeDisabled()
  })

  it("shows preview and finalization failures", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith("/samples?")) return Promise.resolve({ data: { live_samples: [] } })
      return Promise.reject(new Error("Preview failed"))
    })
    mount("/reports?sample_id=SAMPLE_001")
    expect(await screen.findByText("Preview failed")).toBeVisible()

    // Ensure changing an input remains possible while the preview error is visible.
    fireEvent.change(screen.getByPlaceholderText(/Search sample name/), { target: { value: "NEW_SAMPLE" } })
    expect(screen.getByPlaceholderText(/Search sample name/)).toHaveValue("NEW_SAMPLE")
  })
})
