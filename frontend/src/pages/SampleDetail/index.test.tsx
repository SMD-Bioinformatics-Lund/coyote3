import { fireEvent, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { renderWithRouter } from "@/test/render"

const mocks = vi.hoisted(() => ({
  context: {} as Record<string, unknown>,
  analysisLayout: "modern" as "classic" | "modern",
  analysisModernViewTried: false,
  updateUiSettings: vi.fn(),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey, enabled }: { queryKey: unknown[]; enabled?: boolean }) => {
    if (queryKey[0] === "sample") return { data: mocks.context, isLoading: false, error: null }
    if (queryKey[0] === "whoami") {
      return {
        data: {
          ui_settings: {
            analysis_layout: mocks.analysisLayout,
            analysis_modern_view_tried: mocks.analysisModernViewTried,
          },
        },
      }
    }
    return { data: enabled === false ? undefined : { suggested_text: "Suggested" }, isLoading: false, error: null }
  },
  useMutation: () => ({ mutate: mocks.updateUiSettings, isPending: false }),
  useQueryClient: () => ({
    cancelQueries: vi.fn(),
    getQueryData: vi.fn(),
    setQueryData: vi.fn(),
    invalidateQueries: vi.fn(),
  }),
}))

vi.mock("./OverviewTab", () => ({
  BiomarkerRow: () => <div>Biomarkers</div>,
  OverviewTab: () => <div>Overview content</div>,
  PanelSummary: () => <div>Panel summary</div>,
}))
vi.mock("./VariantsTab", () => ({ VariantsTab: ({ intent }: { intent: string }) => <div>{intent} variants</div> }))
vi.mock("./CNVTab", () => ({ CNVTab: () => <div>CNV content</div> }))
vi.mock("./FusionsTab", () => ({ FusionsTab: () => <div>Fusion content</div> }))
vi.mock("./TranslocationsTab", () => ({ TranslocationsTab: () => <div>Translocation content</div> }))
vi.mock("./ReportsTab", () => ({ ReportsTab: () => <div>Reports content</div> }))
vi.mock("./CoverageTab", () => ({ CoverageTab: () => <div>Coverage content</div> }))
vi.mock("./RnaAnalysisTabs", () => ({
  RnaAnalysisTab: () => <div>Expression and classification content</div>,
}))
vi.mock("./FindingsTab", () => ({
  FindingsTab: ({
    sections,
    onSelectFilterSection,
  }: {
    sections: Array<{ label: string }>
    onSelectFilterSection: (section: "cnvs") => void
  }) => (
    <div>
      Findings: {sections.map((section) => section.label).join(", ")}
      <button type="button" onClick={() => onSelectFilterSection("cnvs")}>Open CNV filters</button>
    </div>
  ),
}))
vi.mock("./FiltersSidebar", () => ({
  FiltersSidebar: ({
    intent,
    activeTab,
    toggleRequest,
  }: {
    intent: string
    activeTab: string
    toggleRequest: { sequence: number; section: string } | null
  }) => (
    <div>
      Filters {intent} {activeTab} request {toggleRequest?.sequence ?? 0} section {toggleRequest?.section ?? "none"}
    </div>
  ),
}))
vi.mock("@/components/comments/CommentsPanel", () => ({ CommentsPanel: () => <div>Comments</div> }))

import { SampleDetail } from "./index"

function sampleContext(overrides: Record<string, unknown> = {}) {
  return {
    sample: {
      name: "DNA_001",
      case_id: "CASE_001",
      asp_id: "hema_gmsv1",
      environment: "production",
      ingest_status: "ready",
      omics_layer: "dna",
      analysis_intents: ["somatic", "germline"],
      data_counts: { snvs: 12, cnvs: 3, cov: true },
      ...overrides,
    },
    analysis_sections: ["SNV", "CNV", "COVERAGE"],
  }
}

describe("SampleDetail", () => {
  beforeEach(() => {
    mocks.context = sampleContext()
    mocks.analysisLayout = "modern"
    mocks.analysisModernViewTried = false
    mocks.updateUiSettings.mockReset()
  })

  it("shows only analysis tabs supported by the sample resources and ASPC", () => {
    renderWithRouter(<SampleDetail />, "/samples/DNA_001")

    expect(screen.getByRole("tab", { name: "Overview" })).toBeVisible()
    expect(screen.getByRole("tab", { name: "Somatic SNVs" })).toBeVisible()
    expect(screen.getByRole("tab", { name: "Germline SNVs" })).toBeVisible()
    expect(screen.getByRole("tab", { name: "CNVs" })).toBeVisible()
    expect(screen.getByRole("tab", { name: "Coverage" })).toBeVisible()
    expect(screen.queryByRole("tab", { name: "Fusions" })).not.toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: "Translocations" })).not.toBeInTheDocument()
  })

  it("combines enabled analyses in the persisted classic layout", () => {
    mocks.analysisLayout = "classic"
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=findings")

    expect(screen.getByRole("tab", { name: "Findings" })).toHaveAttribute("aria-selected", "true")
    expect(screen.queryByRole("tab", { name: "Somatic SNVs" })).not.toBeInTheDocument()
    expect(screen.getByText("Findings: Somatic SNVs, Germline SNVs, CNVs")).toBeVisible()
  })

  it("offers modern until the modern analysis layout has been tried", () => {
    mocks.analysisLayout = "classic"
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=findings")

    expect(screen.getByText("Try the modern layout")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Try modern" }))

    expect(mocks.updateUiSettings).toHaveBeenCalledWith({
      analysis_layout: "modern",
      analysis_modern_view_tried: true,
    })
  })

  it("keeps the analysis layout banner dismissed after returning to classic", () => {
    mocks.analysisLayout = "classic"
    mocks.analysisModernViewTried = true
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=findings")

    expect(screen.queryByText("Prefer a focused view?")).not.toBeInTheDocument()
  })

  it("selects and opens the requested section filters from the findings view", () => {
    mocks.analysisLayout = "classic"
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=findings")

    expect(screen.getByText("Filters somatic snvs request 0 section none")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Open CNV filters" }))

    expect(screen.getByText("Filters somatic cnvs request 1 section cnvs")).toBeVisible()
  })

  it("switches between somatic and germline views without mixing intent", () => {
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=snvs")
    expect(screen.getByText("somatic variants")).toBeVisible()
    expect(screen.getByText("Filters somatic snvs request 0 section none")).toBeVisible()

    fireEvent.click(screen.getByRole("tab", { name: "Germline SNVs" }))
    expect(screen.getByText("germline variants")).toBeVisible()
    expect(screen.getByText("Filters germline germline-snvs request 0 section none")).toBeVisible()
  })

  it("does not expose germline or coverage tabs when intent and resources are absent", () => {
    mocks.context = sampleContext({ analysis_intents: ["somatic"], data_counts: { snvs: 2 } })
    renderWithRouter(<SampleDetail />, "/samples/DNA_001")

    expect(screen.getByRole("tab", { name: "Somatic SNVs" })).toBeVisible()
    expect(screen.queryByRole("tab", { name: "Germline SNVs" })).not.toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: "Coverage" })).not.toBeInTheDocument()
  })

  it("omits gene-panel context from the coverage view", () => {
    renderWithRouter(<SampleDetail />, "/samples/DNA_001?tab=coverage")

    expect(screen.getByText("Coverage content")).toBeVisible()
    expect(screen.getByText("Filters somatic coverage request 0 section none")).toBeVisible()
    expect(screen.queryByText("Panel summary")).not.toBeInTheDocument()
  })

  it("shows RNA fusion analysis without DNA-only analysis tabs", () => {
    mocks.context = {
      sample: {
        name: "RNA_001",
        omics_layer: "rna",
        analysis_intents: ["somatic"],
        data_counts: { fusions: 4 },
      },
      analysis_sections: ["FUSION"],
    }
    renderWithRouter(<SampleDetail />, "/samples/RNA_001?tab=fusions")

    expect(screen.getByRole("tab", { name: "Fusions" })).toBeVisible()
    expect(screen.getByText("Fusion content")).toBeVisible()
    expect(screen.queryByRole("tab", { name: "Somatic SNVs" })).not.toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: "CNVs" })).not.toBeInTheDocument()
  })

  it("combines configured WTS expression and classification in one analysis tab", () => {
    mocks.context = {
      sample: {
        name: "WTS_001",
        omics_layer: "rna",
        analysis_intents: ["somatic"],
        data_counts: { fusions: 4, rna_expression: true, rna_classification: true },
      },
      analysis_sections: ["FUSION", "EXPRESSION", "CLASSIFICATION"],
    }
    renderWithRouter(<SampleDetail />, "/samples/WTS_001?tab=rna-analysis")

    expect(screen.getByRole("tab", { name: "Expression & Classification" })).toBeVisible()
    expect(screen.queryByRole("tab", { name: "Classification" })).not.toBeInTheDocument()
    expect(screen.getByText("Expression and classification content")).toBeVisible()
  })

  it("does not infer WTS tabs from files when ASPC omits the analyses", () => {
    mocks.context = {
      sample: {
        name: "RNA_PANEL_001",
        omics_layer: "rna",
        data_counts: { fusions: 2, rna_expression: true, rna_classification: true },
      },
      analysis_sections: ["FUSION"],
    }
    renderWithRouter(<SampleDetail />, "/samples/RNA_PANEL_001")

    expect(screen.queryByRole("tab", { name: "Expression & Classification" })).not.toBeInTheDocument()
  })

  it("keeps old expression links working through the combined RNA analysis tab", () => {
    mocks.context = {
      sample: {
        name: "WTS_001",
        omics_layer: "rna",
        data_counts: { rna_expression: true, rna_classification: true },
      },
      analysis_sections: ["EXPRESSION", "CLASSIFICATION"],
    }
    renderWithRouter(<SampleDetail />, "/samples/WTS_001?tab=expression")

    expect(screen.getByRole("tab", { name: "Expression & Classification" })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("Expression and classification content")).toBeVisible()
  })
})
