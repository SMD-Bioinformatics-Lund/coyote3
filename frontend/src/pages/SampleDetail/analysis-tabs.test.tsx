import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  dataTable: vi.fn(),
  mutateAsync: vi.fn(),
  bulkHook: vi.fn(),
  notifySuccess: vi.fn(),
}))

vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: mocks.notifySuccess, notifyActionError: vi.fn() }))
vi.mock("@/lib/access-control", () => ({
  hasPermission: (_user: unknown, permission: string) => permission === "fusion:manage",
  useCurrentUserAccess: () => ({
    data: { username: "reviewer", roles: [], role: "reviewer", access_level: 10, permissions: ["fusion:manage"] },
  }),
}))
vi.mock("@/hooks/useFindingActions", () => ({
  useBulkFindingAction: (sampleId: string, resourceType: string) => {
    mocks.bulkHook(sampleId, resourceType)
    return { mutateAsync: mocks.mutateAsync, isPending: false }
  },
  useSingleFindingFlag: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
}))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.dataTable(props)
    const columns = (props.columns || []) as any[]
    const rows = (props.data || []) as any[]
    const valueFor = (record: any, id: string) => {
      const column = columns.find((candidate) => candidate.id === id || candidate.accessorKey === id)
      if (column?.accessorFn) return column.accessorFn(record)
      if (column?.accessorKey) return record[column.accessorKey]
      return record[id]
    }
    return (
      <div>
        <div>Table with {String(props.totalCount)} rows</div>
        {rows.length > 0 && typeof props.renderToolbar === "function" && props.renderToolbar({
          getState: () => ({ rowSelection: { 0: true } }),
          getSelectedRowModel: () => ({ rows: [{ original: rows[0] }] }),
        })}
        {rows.slice(0, 1).map((record, rowIndex) => {
          const row = {
            original: record,
            getValue: (id: string) => valueFor(record, id),
            getIsSelected: () => false,
            getToggleSelectedHandler: () => vi.fn(),
          }
          return (
            <div data-testid="rendered-clinical-row" key={record._id || rowIndex}>
              {columns.map((column, columnIndex) => (
                <div key={column.id || column.accessorKey || columnIndex}>
                  {typeof column.cell === "function" ? column.cell({ row }) : String(valueFor(record, column.id) ?? "")}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    )
  },
}))
vi.mock("@/components/layout/ResizableSplitPane", () => ({
  ResizableSplitPane: ({ primary, secondary }: { primary: ReactNode; secondary: ReactNode }) => (
    <div><div>{primary}</div><div>{secondary}</div></div>
  ),
}))
vi.mock("@/components/detail/RotatableImage", () => ({
  RotatableImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}))
vi.mock("@/components/reports/ReportHtmlFrame", () => ({
  ReportHtmlFrame: ({ title, html }: { title: string; html: string }) => <div data-testid="report-frame" data-title={title}>{html}</div>,
}))

import { CNVTab } from "./CNVTab"
import { CoverageTab } from "./CoverageTab"
import { FusionsTab } from "./FusionsTab"
import { ReportsTab } from "./ReportsTab"
import { TranslocationsTab } from "./TranslocationsTab"
import { VariantsTab } from "./VariantsTab"
import { formatPopulationFrequency, variantHotspotEntries } from "@/lib/variant-table-format"

function mount(ui: ReactElement, route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}>{children}</MemoryRouter></QueryClientProvider>
  )
  return render(ui, { wrapper: Wrapper })
}

describe("sample analysis table tabs", () => {
  beforeEach(() => vi.clearAllMocks())

  it("requests and renders somatic variants with server pagination metadata", async () => {
    mocks.get.mockImplementation((url: string) => {
      if (url === "/public/filter-flags/metadata") return Promise.resolve({ data: {} })
      return Promise.resolve({
        data: {
          display_sections_data: { snvs: [{ _id: "V1", INFO: { selected_CSQ: { SYMBOL: "TP53" } } }] },
          meta: { count: 201, page: 1, per_page: 50, has_next: true, has_previous: false },
          sample: { name: "S1", paired: false },
          assay_group: "solid",
        },
      })
    })

    mount(<VariantsTab sampleId="S1" intent="somatic" />, "/samples/S1?tab=snvs")
    expect(await screen.findByText("Table with 201 rows")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith(expect.stringMatching(
      /^\/samples\/S1\/small-variants\?page=1&per_page=50&intent=somatic$/,
    ))
    expect(mocks.dataTable).toHaveBeenLastCalledWith(expect.objectContaining({
      rowLabel: "variants", totalCount: 201, hasNext: true, hasPrevious: false,
    }))
  })

  it("keeps germline requests isolated with the germline intent", async () => {
    mocks.get.mockImplementation((url: string) => url === "/public/filter-flags/metadata"
      ? Promise.resolve({ data: {} })
      : Promise.resolve({ data: { display_sections_data: { snvs: [] }, meta: { count: 0 } } }))

    mount(<VariantsTab sampleId="S2" intent="germline" />, "/samples/S2?tab=germline-snvs&intent=germline")
    expect(await screen.findByText("Table with 0 rows")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining("intent=germline"))
    expect(mocks.get).not.toHaveBeenCalledWith(expect.stringContaining("intent=somatic"))
  })

  it("renders CNV profile only when the sample declares the image resource", async () => {
    mocks.get.mockResolvedValue({
      data: {
        cnvs: [{ _id: "C1", chr: "1", start: 10, end: 20, size: 10, ratio: 0, genes: [] }],
        meta: { count: 1 },
        sample: {
          name: "S3",
          files: { cnvprofile: { path: "/data/S3/profile.png" } },
        },
      },
    })

    mount(<CNVTab sampleId="S3" />, "/samples/S3?tab=cnvs")
    expect(await screen.findByText("Table with 1 rows")).toBeVisible()
    expect(screen.getByText("CNV Profile")).toBeVisible()
    expect(screen.getByRole("img", { name: "CNV profile for S3" })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/S3/cnvs?page=1&per_page=50")
  })

  it("uses the whole table width when no CNV profile exists", async () => {
    mocks.get.mockResolvedValue({ data: { cnvs: [], meta: { count: 0 }, sample: { name: "S4" } } })
    mount(<CNVTab sampleId="S4" />, "/samples/S4?tab=cnvs")
    await waitFor(() => expect(screen.getByText("Table with 0 rows")).toBeVisible())
    expect(screen.queryByText("CNV Profile")).not.toBeInTheDocument()
  })

  it("requests fusion rows with server metadata and fusion-only export context", async () => {
    mocks.get.mockResolvedValue({ data: {
      fusions: [{ _id: "F1", genes: ["BCR", "ABL1"], callers: ["ARRIBA"] }],
      meta: { count: 71, page: 2, per_page: 50, has_next: false, has_previous: true },
    } })
    mount(<FusionsTab sampleId="RNA_1" />, "/samples/RNA_1?tab=fusions&fusion_page=2")

    expect(await screen.findByText("Table with 71 rows")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/RNA_1/fusions?page=2&per_page=50")
    expect(mocks.dataTable).toHaveBeenLastCalledWith(expect.objectContaining({
      rowLabel: "fusions",
      totalCount: 71,
      page: 2,
      hasNext: false,
      hasPrevious: true,
      filename: "fusions_RNA_1.csv",
    }))
  })

  it("supports both current and historical translocation response envelopes", async () => {
    mocks.get.mockResolvedValue({ data: {
      display_sections_data: {
        translocs: [{
          _id: "T1",
          CHROM: "11",
          POS: 100,
          INFO: { MANE_ANN: { Consequence: "gene_fusion" } },
        }],
      },
      meta: { count: 1, page: 1, per_page: 50 },
      vep_conseq_translations: {
        gene_fusion: {
          display_name: "Gene fusion",
          description: "A transcript altered by a structural gene fusion.",
          impact: "HIGH",
        },
      },
    } })
    mount(<TranslocationsTab sampleId="DNA_1" />, "/samples/DNA_1?tab=translocations")

    expect(await screen.findByText("Table with 1 rows")).toBeVisible()
    const typeBadge = screen.getByText("Gene fusion")
    expect(typeBadge).toBeVisible()
    fireEvent.mouseEnter(typeBadge)
    expect(await screen.findByText("A transcript altered by a structural gene fusion.")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_1/translocations?page=1&per_page=50")
    expect(mocks.dataTable).toHaveBeenLastCalledWith(expect.objectContaining({
      rowLabel: "translocations",
      filename: "translocations_DNA_1.csv",
    }))
  })

  it.each([
    ["fusions", <FusionsTab key="fusions" sampleId="S1" />, "Error loading Fusions"],
    ["translocations", <TranslocationsTab key="translocations" sampleId="S1" />, "Error loading Translocations"],
  ])("renders a visible %s failure state", async (_name, component, message) => {
    mocks.get.mockRejectedValue(new Error("network unavailable"))
    mount(component, `/samples/S1?tab=${_name}`)
    expect(await screen.findByText(message)).toBeVisible()
  })

  it("renders coverage metrics, low-gene navigation, and a flattened coverage table", async () => {
    mocks.get.mockResolvedValue({ data: {
      smp_grp: "hematology",
      cov_table: {
        TP53: {
          exon_4: { chr: "17", start: 100, end: 150, cov: 120, exon: 4 },
          exon_5: { chr: "17", start: 200, end: 250, cov: 450, exon: 5 },
        },
      },
      coverage: {
        genes: {
          TP53: {
            transcript: { chr: "17", start: 90, end: 300, id: "NM_000546.6" },
            exons: [{ chr: "17", start: 100, end: 150, cov: 120, nbr: 4 }],
            CDS: [{ chr: "17", start: 105, end: 145, cov: 120, nbr: 4 }],
            probes: [{ chr: "17", start: 110, end: 130, cov: 80 }],
          },
        },
      },
    } })
    mount(<CoverageTab sampleId="DNA_COV" />, "/samples/DNA_COV?tab=coverage")

    expect(await screen.findByText("Low-Coverage Genes")).toBeVisible()
    expect(screen.getAllByText("TP53").length).toBeGreaterThan(0)
    expect(screen.getByText("NM_000546.6")).toBeVisible()
    expect(screen.getByText("Table with undefined rows")).toBeVisible()
    const geneSearch = screen.getByRole("searchbox", { name: "Search low-coverage genes" })
    fireEvent.change(geneSearch, { target: { value: "BRCA" } })
    expect(screen.getByText("No low-coverage genes match BRCA.")).toBeVisible()
    fireEvent.change(geneSearch, { target: { value: "TP53" } })
    expect(screen.getByText("1 of 1 gene(s) below 500X")).toBeVisible()
    const plotViewport = screen.getByRole("region", { name: "TP53 coverage plot viewport" })
    const plot = screen.getByRole("img", { name: "TP53 coverage plot" })
    expect(plotViewport).toHaveClass("overflow-x-auto", "max-w-full")
    expect(plot).toHaveAttribute("width", "1100")
    expect(screen.getByText("Exon design")).toBeVisible()
    expect(screen.getByText("CDS coverage")).toBeVisible()
    expect(screen.getByText("Position")).toBeVisible()
    fireEvent.mouseEnter(screen.getByRole("button", { name: "CDS 4, 17:105-145, 120.00X" }))
    expect(screen.getByText("CDS 4")).toBeVisible()
    expect(screen.getAllByText("17:105-145").some((element) => element.tagName === "P")).toBe(true)
    expect(screen.getByText("40 bp")).toBeVisible()
    expect(screen.getAllByText("120.00X").some((element) => element.tagName === "P")).toBe(true)
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }))
    expect(plot).toHaveAttribute("width", "1375")
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_COV/coverage?cov_cutoff=500")
    expect(mocks.dataTable).toHaveBeenLastCalledWith(expect.objectContaining({
      data: expect.arrayContaining([expect.objectContaining({ gene: "TP53", region: "exon_4", cov: 120 })]),
      filename: "coverage_DNA_COV.csv",
    }))
  })

  it("re-queries coverage when the saved warning threshold changes and shows API errors", async () => {
    mocks.get.mockResolvedValueOnce({ data: { cov_table: {}, coverage: { genes: {} } } })
      .mockRejectedValueOnce(new Error("Coverage unavailable"))
    const { rerender } = mount(
      <CoverageTab sampleId="DNA_COV" sample={{ filters: { somatic: { coverage: { warn_cov: 500 } } } }} />,
      "/samples/DNA_COV?tab=coverage",
    )
    await screen.findByText("No low-covered genes for the current cutoff and selected gene lists.")

    rerender(<CoverageTab sampleId="DNA_COV" sample={{ filters: { somatic: { coverage: { warn_cov: 250 } } } }} />)
    expect(await screen.findByText("Coverage unavailable")).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_COV/coverage?cov_cutoff=250")
  })

  it("renders a report preview and requires confirmation before saving", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "DNA_REPORT" },
      meta: { snapshot_count: 1, template_status: { status: "ready", has_html: true } },
      report: { html: "Rendered DNA report", snapshot_rows: [{ gene: "TP53", tier: 1 }] },
    } })
    mocks.post.mockResolvedValue({ data: { report_id: "R1" } })
    mount(<ReportsTab sampleId="DNA_REPORT" />, "/samples/DNA_REPORT?tab=reports")

    expect(await screen.findByTestId("report-frame")).toHaveTextContent("Rendered DNA report")
    expect(mocks.get).toHaveBeenCalledWith("/samples/DNA_REPORT/reports/dna/preview?include_snapshot=true&save=false")
    fireEvent.click(screen.getByRole("button", { name: "Save report" }))
    expect(screen.getByRole("heading", { name: "Confirm report save" })).toBeVisible()
    expect(mocks.post).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Confirm save" }))

    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/samples/DNA_REPORT/reports/dna"))
    expect(mocks.notifySuccess).toHaveBeenCalledWith(
      "Report saved",
      "DNA report was saved for DNA_REPORT.",
      "Reports",
      expect.objectContaining({ sampleName: "DNA_REPORT" }),
    )
  })

  it("groups every included clinical finding type into its own snapshot table", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "MULTI_REPORT" },
      meta: { snapshot_count: 6, template_status: { status: "ready", has_html: true } },
      report: {
        html: "Rendered multi-analysis report",
        snapshot_rows: [
          { analysis_type: "SNV", gene: "TP53", variant: "p.Arg175His", tier: 1 },
          { analysis_type: "CNV", gene: "EGFR", region: "7:100-300", cnv_type: "gain" },
          { analysis_type: "TRANSLOCATION", gene_1: "KMT2A", gene_2: "AFF1", breakpoint: "11:1" },
          { analysis_type: "FUSION", fusion: "BCR::ABL1", breakpoint_1: "22:1", breakpoint_2: "9:2" },
          { analysis_type: "BIOMARKER", biomarker: "TMB", result: "12.4 mut/Mb" },
          { analysis_type: "PGX", gene: "CYP2C19", pgx_result: "Intermediate metabolizer" },
        ],
      },
    } })

    mount(<ReportsTab sampleId="MULTI_REPORT" />, "/samples/MULTI_REPORT?tab=reports")

    expect(await screen.findByText("Rendered multi-analysis report")).toBeVisible()
    for (const section of [
      "Small variants",
      "Copy-number variants",
      "DNA fusions and translocations",
      "RNA fusions",
      "Biomarkers",
      "Pharmacogenomics",
    ]) {
      expect(screen.getByText(section)).toBeVisible()
    }
    expect(mocks.dataTable).toHaveBeenCalledTimes(6)
    expect(mocks.dataTable.mock.calls.map(([props]) => props.filename)).toEqual([
      "MULTI_REPORT_dna_snv_snapshot.csv",
      "MULTI_REPORT_dna_cnv_snapshot.csv",
      "MULTI_REPORT_dna_translocation_snapshot.csv",
      "MULTI_REPORT_dna_fusion_snapshot.csv",
      "MULTI_REPORT_dna_biomarker_snapshot.csv",
      "MULTI_REPORT_dna_pgx_snapshot.csv",
    ])
  })

  it("uses the fixed RNA report workflow for an RNA sample", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "RNA_REPORT", omics_layer: "rna" },
      meta: { snapshot_count: 1, template_status: { status: "ready", has_html: true } },
      report: {
        html: "Rendered RNA report",
        snapshot_rows: [{
          fusion: "KMT2A::AFF1",
          breakpoint_1: "11:1",
          breakpoint_2: "4:2",
          effect: "in-frame",
          spanning_pairs: 8,
          spanning_reads: 13,
          classification: 2,
          text: "Reviewed fusion",
        }],
      },
    } })
    mount(<ReportsTab sampleId="RNA_REPORT" reportType="rna" />, "/samples/RNA_REPORT?tab=reports")

    expect(await screen.findByTestId("report-frame")).toHaveTextContent("Rendered RNA report")
    expect(mocks.get).toHaveBeenCalledWith("/samples/RNA_REPORT/reports/rna/preview?include_snapshot=true&save=false")
    expect(screen.queryByRole("button", { name: "dna" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "rna" })).not.toBeInTheDocument()
    expect(screen.getByText("KMT2A::AFF1")).toBeVisible()
    expect(screen.getByText("11:1 / 4:2")).toBeVisible()
    expect(screen.getByText("in-frame")).toBeVisible()
    expect(screen.getByText("8 / 13")).toBeVisible()
    expect(screen.getByText("2")).toBeVisible()
    expect(screen.getByText("Reviewed fusion")).toBeVisible()
    const reportTable = mocks.dataTable.mock.calls.at(-1)?.[0]
    expect(reportTable.columns.map((column: { id: string }) => column.id)).toEqual([
      "fusion", "breakpoints", "effect", "support", "classification", "text",
    ])
  })

  it("keeps report actions disabled when no approved HTML is available", async () => {
    mocks.get.mockResolvedValue({ data: {
      sample: { name: "DNA_REPORT" },
      meta: { snapshot_count: 0, template_status: { status: "missing", has_html: false, message: "No reporting rules" } },
      report: { html: "", snapshot_rows: [] },
    } })
    mount(<ReportsTab sampleId="DNA_REPORT" />, "/samples/DNA_REPORT?tab=reports")

    expect(await screen.findByText("No reporting rules")).toBeVisible()
    expect(screen.getByRole("button", { name: "Save report" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "PDF" })).toBeDisabled()
  })

  it.each([
    {
      name: "small variants",
      component: <VariantsTab key="snv-actions" sampleId="ACTION_SAMPLE" intent="somatic" />,
      route: "/samples/ACTION_SAMPLE?tab=somatic-snvs",
      resourceType: "small_variant",
      row: { _id: "SNV_1", INFO: { selected_CSQ: { SYMBOL: "TP53" } } },
      responseKey: "snvs",
      actionLabel: "Classify as Tier 3",
      action: "tier_3",
    },
    {
      name: "CNVs",
      component: <CNVTab key="cnv-actions" sampleId="ACTION_SAMPLE" />,
      route: "/samples/ACTION_SAMPLE?tab=cnvs",
      resourceType: "cnv",
      row: { _id: "CNV_1", chr: "1", start: 10, end: 20, genes: [] },
      responseKey: "cnvs",
      actionLabel: "Include in report",
      action: "interesting",
    },
    {
      name: "fusions",
      component: <FusionsTab key="fusion-actions" sampleId="ACTION_SAMPLE" />,
      route: "/samples/ACTION_SAMPLE?tab=fusions",
      resourceType: "fusion",
      row: { _id: "FUSION_1", genes: ["BCR", "ABL1"], callers: ["ARRIBA"] },
      responseKey: "fusions",
      actionLabel: "Mark Blacklisted",
      action: "blacklisted",
    },
    {
      name: "translocations",
      component: <TranslocationsTab key="translocation-actions" sampleId="ACTION_SAMPLE" />,
      route: "/samples/ACTION_SAMPLE?tab=translocations",
      resourceType: "translocation",
      row: { _id: "TRANSLOC_1", CHROM: "11", POS: 100 },
      responseKey: "translocs",
      actionLabel: "Include in report",
      action: "interesting",
    },
  ])("confirms and submits the approved $name bulk action", async ({ component, route, resourceType, row, responseKey, actionLabel, action }) => {
    mocks.get.mockImplementation((url: string) => url === "/public/filter-flags/metadata"
      ? Promise.resolve({ data: {} })
      : Promise.resolve({ data: { display_sections_data: { [responseKey]: [row] }, [responseKey]: [row], meta: { count: 1 } } }))
    mocks.mutateAsync.mockResolvedValue({})
    mount(component, route)

    await screen.findByText("1 selected")
    expect(mocks.bulkHook).toHaveBeenCalledWith("ACTION_SAMPLE", resourceType)
    fireEvent.change(screen.getByRole("combobox"), { target: { value: action } })
    fireEvent.click(screen.getByRole("button", { name: "Apply" }))
    expect(screen.getByRole("heading", { name: "Confirm bulk action" })).toBeVisible()
    expect(mocks.mutateAsync).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Apply action" }))

    await waitFor(() => expect(mocks.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      action,
      resourceIds: [row._id],
    })))
    expect(screen.queryByText(actionLabel)).not.toBeNull()
  })

  it("cancels a clinical bulk action without mutating persisted state", async () => {
    mocks.get.mockImplementation((url: string) => url === "/public/filter-flags/metadata"
      ? Promise.resolve({ data: {} })
      : Promise.resolve({ data: {
        display_sections_data: { snvs: [{ _id: "SNV_CANCEL", INFO: { selected_CSQ: { SYMBOL: "TP53" } } }] },
        meta: { count: 1 },
      } }))
    mount(<VariantsTab sampleId="ACTION_SAMPLE" intent="somatic" />, "/samples/ACTION_SAMPLE?tab=somatic-snvs")

    await screen.findByText("1 selected")
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "fp" } })
    fireEvent.click(screen.getByRole("button", { name: "Apply" }))
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    expect(mocks.mutateAsync).not.toHaveBeenCalled()
    expect(screen.queryByRole("heading", { name: "Confirm bulk action" })).not.toBeInTheDocument()
  })
})

describe("small-variant table formatting", () => {
  it("formats population frequency percentages with at most six decimal places", () => {
    expect(formatPopulationFrequency(0.00601)).toBe("0.601")
    expect(formatPopulationFrequency(0.000001234567)).toBe("0.000123")
    expect(formatPopulationFrequency(0)).toBe("0")
    expect(formatPopulationFrequency(null)).toBe("-")
  })

  it("normalizes existing hotspot metadata without defining a future list contract", () => {
    expect(variantHotspotEntries({
      hotspots: [{ lu: ["HS1", "HS1", "HS2"] }],
      INFO: { HOTSPOT: ["lu", "co"] },
    })).toEqual([
      { source: "lu", identifiers: ["HS1", "HS2"] },
      { source: "co", identifiers: [] },
    ])
  })

  it("keeps only the latest COSMIC identifier within each hotspot source", () => {
    expect(variantHotspotEntries({
      hotspots: [
        { lu: ["HS1", "COSM6240", "COSV51794834", "COSV66102297"] },
        { co: ["COSM12&COSM91"] },
      ],
    })).toEqual([
      { source: "lu", identifiers: ["HS1", "COSV66102297"] },
      { source: "co", identifiers: ["COSM91"] },
    ])
  })
})
