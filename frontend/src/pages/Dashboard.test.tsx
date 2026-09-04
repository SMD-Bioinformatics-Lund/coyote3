import { fireEvent, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { buildPanelAnalysisCapabilityData, buildPanelGeneChartData } from "@/lib/dashboard-data"
import { Dashboard } from "./Dashboard"

const queryState = vi.hoisted(() => ({
  data: undefined as any,
  isLoading: false,
  error: null as Error | null,
  unavailableIndexes: new Set<number>(),
  refetch: vi.fn(),
}))
const mutationState = vi.hoisted(() => ({
  mutate: vi.fn(),
  isPending: false,
}))
const queryClientState = vi.hoisted(() => ({
  refetchQueries: vi.fn(),
}))
const knowledgebaseState = vi.hoisted(() => ({
  data: {
    releases: [
      { source: "cosmic_cancer_gene_census", release: "104", status: "active", records: 768 },
      { source: "cosmic_mutation_census", release: "104", status: "active", records: 2000 },
      { source: "oncokb_public", release: "Remote service", status: "configured", records: 0 },
      { source: "iarc_tp53", release: "R21", status: "active", records: 3000 },
    ],
    summary: { available_products: 4, total_records: 5768 },
  } as any,
  isLoading: false,
  error: null as Error | null,
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => knowledgebaseState,
  useQueries: () => Array.from({ length: 6 }, (_, index) => ({
    ...queryState,
    error: queryState.unavailableIndexes.has(index) ? new Error("Metric request failed") : queryState.error,
    data: queryState.data && !queryState.unavailableIndexes.has(index)
      ? {
          ...queryState.data,
          metric_meta: {
            metric: `metric_${index}`,
            generated_at: "2026-08-25T10:00:00Z",
            stale: false,
            cache_hit: true,
          },
        }
      : undefined,
  })),
  useQueryClient: () => queryClientState,
  useMutation: () => mutationState,
}))
vi.mock("@/lib/notifications", () => ({
  notifyActionError: vi.fn(),
  notifySuccess: vi.fn(),
  notifyWarning: vi.fn(),
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
  top_tiered_genes: [
    { gene: "TP53", total: 7, tier1: 2, tier2: 3, tier3: 2, tier4: 0, nomenclatures: ["p", "c"] },
    { gene: "BCR", total: 3, tier1: 3, tier2: 0, tier3: 0, tier4: 0, nomenclatures: ["f"] },
  ],
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
  dashboard_meta: {
    snapshot_updated_at: "2026-08-25T10:00:00Z",
    snapshot_stale: false,
  },
  user_scope_summary: {
    total_samples: 7,
    pending_samples: 3,
    analysed_rate_percent: 57.1,
    recent_samples: [{ name: "DNA_CASE_001", asp_id: "hema_gmsv1", subpanel_id: "hem", omics_layer: "dna", ingest_status: "ready", time_added: "2026-08-01T10:00:00Z" }],
    sample_stats: {
      pipelines: [
        { name: "SomaticPanelPipeline", version: "3.2.0", count: 5, analysed: 3, ready: 5 },
        { name: "RnaFusionPipeline", version: null, count: 2, analysed: 1, ready: 2 },
      ],
    },
  },
}

describe("Dashboard page", () => {
  beforeEach(() => {
    queryState.data = dashboardData
    queryState.isLoading = false
    queryState.error = null
    queryState.unavailableIndexes.clear()
    queryState.refetch.mockReset()
    mutationState.mutate.mockReset()
    mutationState.isPending = false
    queryClientState.refetchQueries.mockReset()
    knowledgebaseState.error = null
  })

  it("renders workload, inventory, recent samples, and chart-backed summaries", async () => {
    renderWithRouter(<Dashboard />)

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument()
    expect(screen.getByText("Operations")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open samples" })).toHaveAttribute("href", "/samples")
    expect(screen.getByRole("link", { name: "Variant search" })).toHaveAttribute("href", "/variants/search")
    expect(screen.getByRole("link", { name: "Catalog" })).toHaveAttribute("href", "/public/catalog")
    expect(screen.getByText((_, element) => element?.textContent === "4 of 10 analysed")).toBeInTheDocument()
    expect(
      screen.getByText("Small variant, CNV, fusion, and translocation records."),
    ).toBeInTheDocument()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
    expect(screen.getByText("hema_gmsv1")).toBeInTheDocument()
    expect(await screen.findByText("Tier distribution", {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText("Active panels")).toBeInTheDocument()
    expect(screen.getByText("Ingest status")).toBeInTheDocument()
    expect(screen.getByText("Omics")).toBeInTheDocument()
    expect(screen.getByText("Sequencing scope")).toBeInTheDocument()
    expect(screen.getByText("My profile scope")).toBeInTheDocument()
    expect(screen.getByText("Pairing")).toBeInTheDocument()
    expect(screen.getByText("Pipeline throughput")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Top Tiered Genes" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Knowledgebases online" })).toBeInTheDocument()
    expect(screen.getByText("COSMIC")).toBeInTheDocument()
    expect(screen.getByText("OncoKB")).toBeInTheDocument()
    expect(screen.getByText("IARC TP53")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /details/i })).toHaveAttribute("href", "/knowledgebases")
    expect(screen.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/variants/gene-cohort?gene=TP53")
    expect(screen.getByText("Protein (p)")).toBeInTheDocument()
    expect(screen.getByText("cDNA (c)")).toBeInTheDocument()
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

  it("renders useful empty-state copy for sparse installations", async () => {
    queryState.data = { variant_stats: {}, sample_stats: {}, user_scope_summary: {}, user_samples_stats: {} }
    renderWithRouter(<Dashboard />)

    expect(screen.getByText("No progress data available.")).toBeInTheDocument()
    expect(screen.getByText("No profile data.")).toBeInTheDocument()
    expect(screen.getByText("No recent visible samples.")).toBeInTheDocument()
    expect(await screen.findAllByText("No data", {}, { timeout: 5000 })).toHaveLength(5)
    expect(screen.getByText("No pipeline data available.")).toBeInTheDocument()
    expect(screen.getByText("No tiered gene data available.")).toBeInTheDocument()
  })

  it("shows the loading state", () => {
    queryState.isLoading = true
    queryState.data = undefined
    renderWithRouter(<Dashboard />)

    expect(screen.getByRole("status", { name: "Loading dashboard" })).toBeInTheDocument()
  })

  it("keeps available sections visible when one metric request fails", () => {
    queryState.error = new Error("Metric request failed")
    renderWithRouter(<Dashboard />)

    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
    expect(screen.getByText(/Some dashboard sections could not be updated/)).toBeInTheDocument()
  })

  it("does not present missing first-load metrics as valid zero values", () => {
    queryState.unavailableIndexes.add(2)
    renderWithRouter(<Dashboard />)

    expect(screen.getByText("Top tiered genes is temporarily unavailable.")).toBeInTheDocument()
    expect(screen.queryByText("No tiered gene data available.")).not.toBeInTheDocument()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
  })

  it("queues an explicit background refresh without replacing the current dashboard", () => {
    renderWithRouter(<Dashboard />)

    fireEvent.click(screen.getByRole("button", { name: "Refresh metrics" }))

    expect(mutationState.mutate).toHaveBeenCalledOnce()
    expect(screen.getByText("DNA_CASE_001")).toBeInTheDocument()
  })
})
