import { screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { buildPanelAnalysisCapabilityData, buildPanelGeneChartData } from "@/lib/dashboard-data"
import { Dashboard } from "./Dashboard"

const queryState = vi.hoisted(() => ({
  data: undefined as any,
  isLoading: false,
  error: null as Error | null,
}))

vi.mock("@tanstack/react-query", () => ({ useQuery: () => queryState }))
vi.mock("@/components/dashboard/DashboardCharts", () => ({
  TierDistributionChart: () => <div>Tier chart rendered</div>,
  GeneCoverageChart: ({ data }: { data: Array<{ name: string }> }) => <div>Gene chart rendered: {data.map((row) => row.name).join(", ")}</div>,
  PanelAnalysisCapabilityChart: ({ data }: { data: Array<{ name: string }> }) => <div>Capability chart rendered: {data.map((row) => row.name).join(", ")}</div>,
}))

const dashboardData = {
  total_samples: 10,
  analysed_samples: 4,
  pending_samples: 6,
  variant_stats: {
    snv: 1200,
    cnv: 14,
    fusion: 2,
    translocation: 3,
    unique_variants: 800,
    by_variant_class: { SNV: 900, deletion: 300 },
  },
  user_samples_stats: {
    hema_gmsv1: { total: 5, analysed: 2, pending: 3 },
    tumwgs_hema: { total: 2, analysed: 1, pending: 1 },
  },
  sample_stats: {
    profiles: { production: 8, validation: 2 },
    ingest_statuses: { ready: 10 },
    omics_layers: { dna: 8, rna: 2 },
    sequencing_scopes: { panel: 10 },
    pair_count: { paired: 6, unpaired: 4 },
  },
  tier_stats: { total: { tier1: 4, tier2: 3 } },
  quality_stats: { analysed_rate_percent: 40 },
  capacity_counts: { users: 4, roles: 3 },
  panel_gene_stats_grouped: {
    hematology: [{ asp_id: "hema_gmsv1", display_name: "Hematology", covered_genes_count: 385, germline_genes_count: 20 }],
  },
  panel_portfolio: { active_panels: 1, assay_groups: 1, covered_gene_assignments: 385, germline_gene_assignments: 20, accredited_panels: 1 },
  panel_analysis_capabilities: [
    { analysis_type: "SNV", enabled: 2, reportable: 2 },
    { analysis_type: "CNV", enabled: 2, reportable: 1 },
  ],
  user_scope_summary: {
    total_samples: 7,
    pending_samples: 3,
    analysed_rate_percent: 57.1,
    recent_samples: [{ name: "DNA_CASE_001", asp_id: "hema_gmsv1", subpanel_id: "hem", omics_layer: "dna", ingest_status: "ready", time_added: "2026-08-01T10:00:00Z" }],
  },
}

describe("Dashboard page", () => {
  beforeEach(() => {
    queryState.data = dashboardData
    queryState.isLoading = false
    queryState.error = null
  })

  it("renders workload, inventory, recent samples, and chart-backed summaries", async () => {
    renderWithRouter(<Dashboard />)

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument()
    expect(screen.getByText((_, element) => element?.textContent === "4 of 10 analysed")).toBeInTheDocument()
    expect(screen.getByText("800 unique small variants across visible samples.")).toBeInTheDocument()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
    expect(screen.getByText("hema_gmsv1")).toBeInTheDocument()
    expect(await screen.findByText("Tier chart rendered")).toBeInTheDocument()
    expect(screen.getByText("Active panels")).toBeInTheDocument()
    expect(screen.queryByText("No active panel gene counts available")).not.toBeInTheDocument()
  })

  it("shows at most five recent samples and links to the complete sample list", () => {
    queryState.data = {
      ...dashboardData,
      user_scope_summary: {
        ...dashboardData.user_scope_summary,
        recent_samples: Array.from({ length: 6 }, (_, index) => ({
          name: `DNA_CASE_00${index + 1}`,
          omics_layer: "dna",
          ingest_status: "ready",
        })),
      },
    }

    renderWithRouter(<Dashboard />)

    expect(screen.getByText("DNA_CASE_005")).toBeInTheDocument()
    expect(screen.queryByText("DNA_CASE_006")).not.toBeInTheDocument()
    expect(screen.getByText("Showing up to 5 most recent samples.")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /view all samples/i })).toHaveAttribute("href", "/samples")
  })

  it("builds panel coverage and analysis capability chart data", () => {
    const geneData = buildPanelGeneChartData({
      hematology: [{ asp_id: "hema_gmsv1", display_name: "Hematology GMSv1", covered_genes_count: 385, germline_genes_count: 20 }],
    })
    const capabilities = buildPanelAnalysisCapabilityData([
      { analysis_type: "SNV", enabled: 3, reportable: 2 },
      { analysis_type: "CNV", enabled: 2, reportable: 1 },
    ])

    expect(geneData).toEqual([{ aspId: "hema_gmsv1", name: "Hematology GMSv1", Covered: 385, Germline: 20 }])
    expect(capabilities).toEqual([
      { name: "SNV", Enabled: 3, Reportable: 2 },
      { name: "CNV", Enabled: 2, Reportable: 1 },
    ])
  })

  it("renders useful empty-state copy for sparse installations", () => {
    queryState.data = { variant_stats: {}, sample_stats: {}, user_scope_summary: {}, user_samples_stats: {} }
    renderWithRouter(<Dashboard />)

    expect(screen.getByText("No progress data available.")).toBeInTheDocument()
    expect(screen.getByText("No profile data.")).toBeInTheDocument()
    expect(screen.getByText("No recent visible samples.")).toBeInTheDocument()
  })

  it("shows loading and API error states", () => {
    queryState.isLoading = true
    const loading = renderWithRouter(<Dashboard />)
    expect(screen.getByRole("status", { name: "Loading dashboard" })).toBeInTheDocument()
    loading.unmount()

    queryState.isLoading = false
    queryState.error = new Error("Summary request failed")
    renderWithRouter(<Dashboard />)
    expect(screen.getByText("Summary request failed")).toBeInTheDocument()
  })
})
