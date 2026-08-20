import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: mocks }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))

import { BiomarkerRow, OverviewTab, PanelSummary } from "./OverviewTab"

function wrapper(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const sample = {
  name: "CASE_001",
  case_id: "CASE_001",
  control_id: "CONTROL_001",
  paired: true,
  ingest_status: "ready",
  time_added: "2026-07-31T08:00:00Z",
  omics_layer: "DNA",
  platform: "illumina",
  read_mode: "paired-end",
  sequencing_scope: "panel",
  genome_build: 38,
  environment: "production",
  asp_id: "hema_gmsv1",
  pipeline: "SomaticPanelPipeline",
  pipeline_version: "3.2.0",
  case: { id: "CASE_001", clarity_id: "CLARITY_CASE", clarity_pool_id: "POOL_CASE", sequencing_run: "RUN_01", reads: 1200, ffpe: false, purity: 0.72 },
  control: { id: "CONTROL_001", clarity_id: "CLARITY_CONTROL", clarity_pool_id: "POOL_CONTROL", sequencing_run: "RUN_01", reads: 1100, ffpe: false },
  files: { vcf_files: "/data/case.vcf", cnv: "/data/case.cnv.json" },
  data_counts: { snv: 1421, cnv: 3, cov: true },
  filters: {
    somatic: {
      snv: { min_depth: 100, snvlists: ["heme"] },
      cnv: { min_cnv_size: 5000, cnvlists: ["heme_cnv"] },
      coverage: { warn_cov: 100, error_cov: 50 },
    },
  },
  aspc_resolution: {
    used_base_configuration: true,
    requested_subpanel_id: "mpn",
    warning: "No subpanel-specific ASPC is active.",
  },
  reports: [{ _id: "REPORT_1", report_name: "Clinical report", created_at: "2026-08-01T10:00:00Z" }],
}

const context = {
  analysis_sections: ["snv", "cnv", "coverage"],
  analysis_counts_raw: { snv: 1421, cnv: 3 },
  analysis_counts_filtered: { snv: 187, cnv: 2 },
  sample_expected_files: [
    { key: "vcf_files", analysis_type: "SNV", path: "/data/case.vcf", required: true, present: true, exists: true, size_bytes: 2048, data_count: 1421, availability: "available" },
    { key: "biomarkers", analysis_type: "BIOMARKER", required: false, present: false, exists: false, availability: "optional_missing" },
  ],
  biomarkers: [{ MSIS: { perc: 0.12, tot: 100, som: 12 }, HRD: { sum: 21, tai: 6, hrd: 7, lst: 8 } }],
  snv_genelist_options: [{ isgl_id: "heme", display_name: "Hematology", gene_count: 197 }],
  cnvlist_options: [{ isgl_id: "heme_cnv", display_name: "Hematology CNV", gene_count: 85 }],
  selected_gene_panels: {
    snv: { lists: [{ id: "heme", name: "Hematology", target: "SNV", gene_count: 3, covered_count: 2, genes: ["TP53", "FLT3", "NPM1"], covered: ["TP53", "FLT3"], uncovered: ["NPM1"], is_active: true }] },
  },
}

describe("sample overview presentation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockImplementation((url: string) => Promise.resolve({
      data: url.includes("effective-genes")
        ? { items: ["TP53", "FLT3"], asp_covered_genes_count: 2 }
        : { items: [{ isgl_id: "heme", name: "Hematology", gene_count: 197, version: 1 }] },
    }))
    mocks.put.mockResolvedValue({ data: {} })
    mocks.post.mockResolvedValue({ data: { meta: { applied_aspc: { aspc_id: "hema_gmsv1_base_production", version: 2 } } } })
    mocks.delete.mockResolvedValue({ data: {} })
  })

  it("renders only valid biomarker values with informative tooltips", async () => {
    const user = userEvent.setup()
    wrapper(<BiomarkerRow context={context} />)
    expect(screen.getByText("MSI (Single):")).toBeVisible()
    expect(screen.getByText("0.12%")).toBeVisible()
    expect(screen.getByText("HRD:")).toBeVisible()
    expect(screen.getByText("21")).toBeVisible()
    await user.hover(screen.getByText("MSI (Single):"))
    expect(screen.getByText("Total: 100; Somatic: 12")).toBeVisible()
  })

  it("renders case purity as a percentage summary", async () => {
    const user = userEvent.setup()
    wrapper(<BiomarkerRow sample={sample} />)
    expect(screen.getByText("Purity:")).toBeVisible()
    expect(screen.getByText("72%")).toBeVisible()
    await user.hover(screen.getByText("Purity:"))
    expect(screen.getByText(/Estimated tumor purity/)).toBeVisible()
  })

  it("renders the FFPE summary only for FFPE case material", async () => {
    const user = userEvent.setup()
    const { rerender } = wrapper(<BiomarkerRow sample={{ ...sample, case: { ...sample.case, ffpe: true } }} />)
    expect(screen.getByText("FFPE:")).toBeVisible()
    expect(screen.getByText("Yes")).toBeVisible()
    await user.hover(screen.getByText("FFPE:"))
    expect(screen.getByText(/formalin-fixed, paraffin-embedded/)).toBeVisible()

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><BiomarkerRow sample={sample} /></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.queryByText("FFPE:")).not.toBeInTheDocument()
  })

  it("summarizes selected panels and expands gene-level coverage", async () => {
    const user = userEvent.setup()
    wrapper(<PanelSummary sample={sample} context={context} />)
    expect(screen.getByText("1 selected list")).toBeVisible()
    expect(screen.getByText("2 / 3 covered")).toBeVisible()
    await user.click(screen.getByRole("button", { name: /Gene Panel/ }))
    expect(screen.getByText("TP53")).toHaveAttribute("title", "This gene is covered in the panel")
    expect(screen.getByText("NPM1")).toHaveAttribute("title", "This gene is not covered in the panel")
  })

  it("shows the clinical sample summary, selected analyses, fallback warning, and files", async () => {
    wrapper(<OverviewTab sampleId="CASE_001" sample={sample} context={context} />)

    expect(screen.getByRole("heading", { name: /^CASE_001/ })).toBeVisible()
    expect(screen.getByText("Paired")).toBeVisible()
    expect(screen.getByText("Unreported")).toBeVisible()
    expect(screen.getByText("1.4K raw")).toBeVisible()
    expect(screen.getByText("187 filtered")).toBeVisible()
    expect(screen.getByText("3 raw")).toBeVisible()
    expect(screen.getByText("2 filtered")).toBeVisible()
    expect(screen.getByText("filter on demand")).toBeVisible()
    expect(screen.queryByText("Fusions")).not.toBeInTheDocument()

    expect(screen.getByText("Base configuration in use.")).toBeVisible()
    expect(screen.getByText("mpn")).toBeVisible()
    expect(screen.getByText("VCF")).toBeVisible()
    expect(screen.getByText("2.0 KB")).toBeVisible()
    expect(screen.getByText("Optional missing")).toBeVisible()
    expect(screen.getByText("No biomarkers file available")).toBeVisible()
    expect(screen.getByRole("heading", { name: "SNV filters" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "CNV filters" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Coverage filters" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Fusion filters" })).not.toBeInTheDocument()
  })

  it("shows the recorded ASPC and newer revision notice", () => {
    wrapper(
      <OverviewTab
        sampleId="CASE_001"
        sample={{ ...sample, current_aspc_key: "hema_gmsv1_base_production", current_aspc_version: 1 }}
        context={{
          ...context,
          aspc_update: {
            available: true,
            latest_aspc_id: "hema_gmsv1_base_production",
            latest_version: 2,
          },
        }}
      />,
    )

    expect(screen.getByText(/ASPC: hema_gmsv1_base_production v1/)).toBeVisible()
    expect(screen.getByText(/Newer ASPC available: hema_gmsv1_base_production v2/)).toBeVisible()
    expect(screen.getByRole("button", { name: "Apply latest ASPC" })).toBeVisible()
  })

  it("shows only RNA fusion filters for an RNA sample", () => {
    const rnaSample = {
      ...sample,
      name: "RNA_001",
      case_id: "RNA_001",
      omics_layer: "RNA",
      paired: false,
      control: undefined,
      filters: {
        somatic: {
          fusion: {
            fusion_callers: ["fusioncatcher", "starfusion"],
            fusion_effects: ["in-frame"],
            fusionlists: ["rna_core"],
            min_spanning_pairs: 3,
            min_spanning_reads: 5,
          },
        },
      },
    }
    wrapper(<OverviewTab sampleId="RNA_001" sample={rnaSample} context={{ analysis_sections: ["fusion"] }} />)

    expect(screen.getByRole("heading", { name: "Fusion filters" })).toBeVisible()
    expect(screen.getByText("fusioncatcher, starfusion")).toBeVisible()
    expect(screen.getAllByText("rna_core").length).toBeGreaterThan(0)
    expect(screen.queryByRole("heading", { name: "SNV filters" })).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "CNV filters" })).not.toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Coverage filters" })).not.toBeInTheDocument()
  })

  it("presents case and control values as aligned columns", () => {
    wrapper(<OverviewTab sampleId="CASE_001" sample={sample} context={context} />)
    const table = screen.getByRole("table")
    expect(within(table).getByRole("columnheader", { name: "Case" })).toBeVisible()
    expect(within(table).getByRole("columnheader", { name: "Control" })).toBeVisible()
    expect(within(table).getByText("CLARITY_CASE")).toBeVisible()
    expect(within(table).getByText("CLARITY_CONTROL")).toBeVisible()
    expect(within(table).getByText("72%")).toBeVisible()
  })

  it("links saved reports to their view and download endpoints", () => {
    wrapper(<OverviewTab sampleId="CASE_001" sample={sample} context={context} />)
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/samples/CASE_001/reports/REPORT_1")
    expect(screen.getByRole("link", { name: "Download" }).getAttribute("href")).toContain("/samples/CASE_001/reports/REPORT_1/download")
  })

  it("shows missing analysis and not-paired states without fabricating control values", () => {
    const unpaired = {
      ...sample,
      paired: false,
      control: undefined,
      data_counts: {},
      files: {},
      reports: [],
      aspc_resolution: undefined,
    }
    wrapper(<OverviewTab sampleId="CASE_002" sample={unpaired} context={{ analysis_sections: ["snv"] }} />)
    expect(screen.getByText("Unpaired")).toBeVisible()
    expect(screen.getByText("Missing")).toBeVisible()
    expect(screen.getAllByText("Not paired").length).toBeGreaterThan(1)
    expect(screen.queryByText("Base configuration in use.")).not.toBeInTheDocument()
  })
})
