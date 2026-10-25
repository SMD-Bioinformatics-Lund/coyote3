import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: mocks }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))

import { OverviewTab } from "./OverviewTab"
import { PanelSummary } from "./PanelSummary"

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
  asp_category: "DNA",
  platform: "illumina",
  read_mode: "paired-end",
  asp_family: "panel-dna",
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
  reports: [{ _id: "REPORT_1", report_name: "Clinical report", created_at: "2026-08-01T10:00:00Z" }],
}

const context = {
  assay_config: {
    aspc_resolution: {
      used_base_configuration: true,
      requested_diagnosis_id: "mpn",
      warning: "No diagnosis-specific assay configuration is active.",
    },
  },
  analysis_sections: ["snv", "cnv", "coverage"],
  analysis_counts_raw: { snv: 1421, cnv: 3 },
  analysis_counts_filtered: { snv: 187, cnv: 2 },
  sample_expected_files: [
    { key: "vcf_files", analysis_type: "SNV", path: "/data/case.vcf", required: true, present: true, exists: true, size_bytes: 2048, data_count: 1421, availability: "available" },
    { key: "biomarkers", analysis_type: null, required: false, present: false, exists: false, availability: "optional_missing" },
  ],
  biomarkers: [{ MSIS: { per: 0.12, tot: 100, som: 12 }, HRD: { sum: 21, tai: 6, hrd: 7, lst: 8 } }],
  snv_genelist_options: [{ isgl_id: "heme", display_name: "Hematology", gene_count: 197 }],
  cnvlist_options: [{ isgl_id: "heme_cnv", display_name: "Hematology CNV", gene_count: 85 }],
  selected_gene_panels: {
    snv: { lists: [{ id: "heme", name: "Hematology", target: "SNV", gene_count: 3, covered_count: 2, genes: ["TP53", "FLT3", "NPM1"], covered: ["TP53", "FLT3"], uncovered: ["NPM1"], is_active: true }] },
  },
}

describe("sample overview presentation", () => {
  it("shows each intent's excluded flags beside its other SNV filters", () => {
    wrapper(<OverviewTab sampleId="CASE_001" context={context} sample={{
      ...sample, analysis_intents: ["somatic", "germline"], filters: {
        ...sample.filters,
        somatic: { ...sample.filters.somatic, snv: {
          ...sample.filters.somatic.snv, exclude_flags: ["WARN_NOVAR"],
        } },
        germline: { snv: { min_depth: 30, exclude_flags: ["FAIL_NVAF"] } },
      },
    }} />)
    const somatic = screen.getByRole("region", { name: "Somatic SNV filters" })
    const germline = screen.getByRole("region", { name: "Germline SNV filters" })
    expect(within(somatic).getByText("Excluded filter flags")).toBeVisible()
    expect(within(somatic).getByText("WARN_NOVAR")).toBeVisible()
    expect(within(germline).getByText("FAIL_NVAF")).toBeVisible()
    expect(within(germline).getByText("Minimum depth")).toBeVisible()
    expect(within(germline).queryByText("Maximum control VAF")).toBeNull()
  })
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

  it("summarizes selected panels and expands gene-level coverage", async () => {
    const user = userEvent.setup()
    wrapper(<PanelSummary sample={sample} context={context} />)
    expect(screen.getByText("1 selected list")).toBeVisible()
    expect(screen.getByText("2 / 3 covered")).toBeVisible()
    await user.click(screen.getByRole("button", { name: /Gene Panel/ }))
    expect(screen.getByText("TP53")).toHaveAttribute("title", "This gene is covered in the panel")
    expect(screen.getByText("NPM1")).toHaveAttribute("title", "This gene is not covered in the panel")
  })

  it("shows the clinical sample summary, fallback warning, and files", async () => {
    wrapper(<OverviewTab sampleId="CASE_001" sample={sample} context={context} />)

    expect(screen.getByText("Base configuration in use.")).toBeVisible()
    expect(screen.getByText("mpn")).toBeVisible()
    expect(screen.getByText("VCF")).toBeVisible()
    expect(screen.getByText("2.0 KB")).toBeVisible()
    expect(screen.getByText("Not available")).toBeVisible()
    expect(screen.getByText("No biomarker file available")).toBeVisible()
    expect(screen.getByText("Biomarker JSON (HRD / MSI / TMB)")).toBeVisible()
    expect(screen.getByRole("heading", { name: "SNV filters" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "CNV filters" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Coverage filters" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Fusion filters" })).not.toBeInTheDocument()
  })

  it("shows the recorded ASPC and newer revision notice", () => {
    wrapper(
      <OverviewTab
        sampleId="CASE_001"
        sample={sample}
        context={{
          ...context,
          assay_config: { aspc_id: "hema_gmsv1_base_production", version: 1 },
          aspc_update: {
            available: true,
            latest_aspc_id: "hema_gmsv1_base_production",
            latest_version: 2,
          },
        }}
      />,
    )

    expect(screen.getByText(/Configuration: hema_gmsv1_base_production v1/)).toBeVisible()
    expect(screen.getByText(/Newer assay configuration available: hema_gmsv1_base_production v2/)).toBeVisible()
    expect(screen.getByRole("button", { name: "Review configuration update" })).toBeVisible()
  })

  it("shows only RNA fusion filters for an RNA sample", () => {
    const rnaSample = {
      ...sample,
      name: "RNA_001",
      case_id: "RNA_001",
      asp_category: "RNA",
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

  it("shows not-paired states without fabricating control values", () => {
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
    expect(screen.getAllByText("Not paired").length).toBeGreaterThan(1)
    expect(screen.queryByText("Base configuration in use.")).not.toBeInTheDocument()
  })

})
