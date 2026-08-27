import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { Samples } from "./Samples"

const queryState = vi.hoisted(() => ({
  data: undefined as any,
  isLoading: false,
  error: null as Error | null,
  user: {
    ui_settings: {
      analysis_layout: "classic",
      sample_list_layout: "classic",
      analysis_modern_view_tried: false,
      sample_list_modern_view_tried: false,
    },
  } as any,
  mutate: vi.fn(),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => queryKey[0] === "whoami"
    ? { data: queryState.user, isLoading: false, error: null }
    : queryState,
  useMutation: () => ({ mutate: queryState.mutate, isPending: false }),
  useQueryClient: () => ({
    cancelQueries: vi.fn(),
    getQueryData: vi.fn(),
    setQueryData: vi.fn(),
    invalidateQueries: vi.fn(),
  }),
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
      data_counts: { snvs: 2100, cnvs: 3, cov: true, biomarkers: false },
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
      latest_report_on: "2026-08-02T12:30:00Z",
      data_counts: { snvs: 8, biomarkers: true },
    },
  ],
  live_total: 2,
  done_total: 1,
  has_next_live: false,
  has_next_done: false,
}

describe("Samples page", () => {
  beforeEach(() => {
    queryState.data = samples
    queryState.isLoading = false
    queryState.error = null
    queryState.user = {
      ui_settings: {
        analysis_layout: "classic",
        sample_list_layout: "classic",
        analysis_modern_view_tried: false,
        sample_list_modern_view_tried: false,
      },
    }
    queryState.mutate.mockReset()
  })

  it("renders live clinical samples and compact count badges", () => {
    renderWithRouter(<Samples />, "/samples")

    expect(screen.getByRole("heading", { name: "Samples" })).toBeInTheDocument()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
    expect(screen.getByText("SNV 2.1K")).toBeInTheDocument()
    expect(screen.getByText("CNV 3")).toBeInTheDocument()
    expect(screen.getByText("Cov")).toBeInTheDocument()
    expect(screen.getByText("SNV 2.1K")).toHaveClass("matte-badge-pass")
    expect(screen.getByText("CNV 3")).toHaveClass("matte-badge-pass")
    expect(screen.getByText("Cov")).toHaveClass("matte-badge-pass")
    const biomarkerBadges = screen.getAllByText("Biomarkers")
    expect(biomarkerBadges.some((badge) => badge.classList.contains("matte-badge-fail"))).toBe(true)
    expect(biomarkerBadges.some((badge) => badge.classList.contains("matte-badge-pass"))).toBe(true)
    expect(screen.getByText("Fusion 3.6K")).toBeInTheDocument()
    expect(screen.getByText("Expr")).toBeInTheDocument()
    expect(screen.getByText("Class")).toBeInTheDocument()
    expect(screen.getByText("QC")).toBeInTheDocument()
    expect(screen.queryByText("RNA EXPR")).not.toBeInTheDocument()
    expect(screen.queryByText("RNA CLASS")).not.toBeInTheDocument()
    expect(screen.queryByText("RNA QC")).not.toBeInTheDocument()
    expect(screen.getByText("DNA_REPORTED_001")).toBeInTheDocument()
    expect(screen.getByText("Try the modern layout")).toBeInTheDocument()
  })

  it("switches to reported samples and preserves the state in the URL", async () => {
    const user = userEvent.setup()
    queryState.user = {
      ui_settings: {
        analysis_layout: "classic",
        sample_list_layout: "modern",
        analysis_modern_view_tried: false,
        sample_list_modern_view_tried: true,
      },
    }
    renderWithRouter(<Samples />, "/samples")

    expect(screen.queryByRole("columnheader", { name: /Latest reported/ })).not.toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: /Reported samples/ }))
    expect(await screen.findByText("DNA_REPORTED_001")).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: /Latest reported/ })).toBeInTheDocument()
    expect(screen.getByTitle(/Aug 2, 2026/)).toBeInTheDocument()
    expect(screen.getByText("Samples with saved clinical reports.")).toBeInTheDocument()
    expect(screen.queryByText("DNA_CASE_001")).not.toBeInTheDocument()
  })

  it("offers modern once and records the sample-list acknowledgement", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples")

    await user.click(screen.getByRole("button", { name: "Try modern" }))

    expect(queryState.mutate).toHaveBeenCalledWith({
      sample_list_layout: "modern",
      sample_list_modern_view_tried: true,
    })
  })

  it("keeps the discovery banner dismissed after returning to classic", () => {
    queryState.user = {
      ui_settings: {
        analysis_layout: "classic",
        sample_list_layout: "classic",
        analysis_modern_view_tried: false,
        sample_list_modern_view_tried: true,
      },
    }

    renderWithRouter(<Samples />, "/samples")

    expect(screen.queryByText("Try the modern layout")).not.toBeInTheDocument()
  })

  it("submits and clears URL-backed search filters", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples?assay=hema_gmsv1&profile_scope=all")

    expect(screen.getByText("all profiles")).toBeInTheDocument()
    expect(screen.getAllByText("hema_gmsv1")).not.toHaveLength(0)
    await user.type(screen.getByPlaceholderText("Search samples..."), "CASE_001")
    await user.click(screen.getByRole("button", { name: "Search" }))
    expect(await screen.findByText("Search: CASE_001")).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: "Clear All" }))
    await waitFor(() => expect(screen.queryByText("Search: CASE_001")).not.toBeInTheDocument())
  })

  it("keeps date presets, custom dates, and row limits in URL-backed controls", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples")

    await user.selectOptions(screen.getByLabelText("Date added"), "custom")
    expect(screen.getByLabelText("From")).toBeInTheDocument()
    expect(screen.getByLabelText("Until")).toBeInTheDocument()
    await user.type(screen.getByLabelText("From"), "2026-08-01")
    await user.type(screen.getByLabelText("Until"), "2026-08-03")
    await user.click(screen.getByRole("button", { name: "Apply dates" }))
    await user.selectOptions(screen.getByLabelText("Maximum rows per page"), "100")

    expect(screen.getByLabelText("From")).toHaveValue("2026-08-01")
    expect(screen.getByLabelText("Until")).toHaveValue("2026-08-03")
    expect(screen.getByLabelText("Maximum rows per page")).toHaveValue("100")
    expect(screen.getAllByText("Custom range")).toHaveLength(2)
  })

  it("keeps invalid custom date drafts open without applying them", async () => {
    const user = userEvent.setup()
    renderWithRouter(<Samples />, "/samples?date_range=custom")

    await user.type(screen.getByLabelText("From"), "2026-08-03")
    await user.type(screen.getByLabelText("Until"), "2026-08-01")

    expect(screen.getByRole("alert")).toHaveTextContent("The From date must be before or equal to the Until date.")
    expect(screen.getByRole("button", { name: "Apply dates" })).toBeDisabled()
    expect(screen.getByLabelText("From")).toHaveValue("2026-08-03")
    expect(screen.getByLabelText("Until")).toHaveValue("2026-08-01")
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
    queryState.data = { live_samples: [], done_samples: [], live_total: 0, done_total: 0 }
    renderWithRouter(<Samples />)
    expect(screen.getAllByText("No samples found.")).toHaveLength(2)
  })

  it("paginates the complete matching result set", async () => {
    const user = userEvent.setup()
    queryState.user = {
      ui_settings: {
        analysis_layout: "classic",
        sample_list_layout: "modern",
        analysis_modern_view_tried: false,
        sample_list_modern_view_tried: true,
      },
    }
    queryState.data = {
      ...samples,
      live_total: 102,
      has_next_live: true,
    }

    renderWithRouter(<Samples />, "/samples?search_str=CASE&sample_per_page=50")

    expect(screen.getByText("Showing 1-2 of 102 samples")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Next" }))
    expect(await screen.findByText("Page 2")).toBeInTheDocument()
    expect(screen.getByText("Search: CASE")).toBeInTheDocument()
  })
})
