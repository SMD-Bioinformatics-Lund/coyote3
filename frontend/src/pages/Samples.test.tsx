import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { Samples } from "./Samples"

const queryState = vi.hoisted(() => ({
  data: undefined as any,
  isLoading: false,
  error: null as Error | null,
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => queryState,
}))

const samples = {
  live_samples: [
    {
      name: "DNA_CASE_001",
      case_id: "CASE_001",
      case: { clarity_id: "CLARITY_001" },
      environment: "production",
      asp_id: "hema_gmsv1",
      subpanel_id: "hem",
      ingest_status: "ready",
      time_added: "2026-08-01T10:00:00Z",
      data_counts: { snvs: 2100, cnvs: 3, cov: true },
    },
    {
      name: "RNA_CASE_001",
      case_id: "RNA_CASE_001",
      environment: "production",
      asp_id: "solidrna_gmsv5",
      subpanel_id: "base",
      ingest_status: "ready",
      time_added: "2026-08-01T11:00:00Z",
      data_counts: {
        fusions: 3600,
        rna_expr: true,
        rna_class: true,
        rna_qc: true,
      },
    },
  ],
  done_samples: [
    {
      name: "DNA_REPORTED_001",
      case_id: "CASE_REPORTED_001",
      environment: "production",
      asp_id: "solid_gmsv3",
      subpanel_id: "colon",
      ingest_status: "ready",
      reported: true,
      time_added: "2026-07-30T10:00:00Z",
      data_counts: { snvs: 8, biomarkers: true },
    },
  ],
}

describe("Samples page", () => {
  beforeEach(() => {
    queryState.data = samples
    queryState.isLoading = false
    queryState.error = null
  })

  it("renders live clinical samples and compact count badges", () => {
    renderWithRouter(<Samples />, "/samples")

    expect(screen.getByRole("heading", { name: "Samples" })).toBeInTheDocument()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
    expect(screen.getByText("SNV 2.1K")).toBeInTheDocument()
    expect(screen.getByText("CNV 3")).toBeInTheDocument()
    expect(screen.getByText("Cov")).toBeInTheDocument()
    expect(screen.getByText("Fusion 3.6K")).toBeInTheDocument()
    expect(screen.getByText("Expr")).toBeInTheDocument()
    expect(screen.getByText("Class")).toBeInTheDocument()
    expect(screen.getByText("QC")).toBeInTheDocument()
    expect(screen.queryByText("RNA EXPR")).not.toBeInTheDocument()
    expect(screen.queryByText("RNA CLASS")).not.toBeInTheDocument()
    expect(screen.queryByText("RNA QC")).not.toBeInTheDocument()
    expect(screen.queryByText("DNA_REPORTED_001")).not.toBeInTheDocument()
  })

  it("switches to reported samples and preserves the state in the URL", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples")

    await user.click(screen.getByRole("tab", { name: /Reported samples/ }))
    expect(await screen.findByText("DNA_REPORTED_001")).toBeInTheDocument()
    expect(screen.getByText("reported")).toBeInTheDocument()
    expect(screen.queryByText("DNA_CASE_001")).not.toBeInTheDocument()
  })

  it("submits and clears URL-backed search filters", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples?assay=hema_gmsv1&profile_scope=all")

    expect(screen.getByText("all profiles")).toBeInTheDocument()
    expect(screen.getAllByText("hema_gmsv1")).not.toHaveLength(0)
    await user.type(screen.getByPlaceholderText("Search by Case ID..."), "CASE_001")
    await user.click(screen.getByRole("button", { name: "Search" }))
    expect(await screen.findByText("Search: CASE_001")).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: "Clear All" }))
    await waitFor(() => expect(screen.queryByText("Search: CASE_001")).not.toBeInTheDocument())
  })

  it("shows loading, failure, and empty states", () => {
    queryState.isLoading = true
    const loading = renderWithRouter(<Samples />)
    expect(screen.getByRole("status", { name: "Loading samples" })).toBeInTheDocument()
    loading.unmount()

    queryState.isLoading = false
    queryState.error = new Error("Database unavailable")
    const failed = renderWithRouter(<Samples />)
    expect(screen.getByText("Failed to load samples")).toBeInTheDocument()
    expect(screen.getByText("Database unavailable")).toBeInTheDocument()
    failed.unmount()

    queryState.error = null
    queryState.data = { live_samples: [], done_samples: [] }
    renderWithRouter(<Samples />)
    expect(screen.getByText("No samples found.")).toBeInTheDocument()
  })
})
