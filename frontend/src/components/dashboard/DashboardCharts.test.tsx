import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  chartPanel: vi.fn(),
  cells: vi.fn(),
  pie: vi.fn(),
  scatterChart: vi.fn(),
  scatters: vi.fn(),
}))
vi.mock("@/components/plots/ChartPanel", () => ({
  ChartPanel: (props: Record<string, unknown>) => {
    mocks.chartPanel(props)
    return <section aria-label={String(props.title)}>{props.children as React.ReactNode}</section>
  },
}))
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: ({ children, ...props }: { children: React.ReactNode }) => { mocks.pie(props); return <div>{children}</div> },
  Cell: (props: Record<string, unknown>) => { mocks.cells(props); return <span /> },
  ScatterChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.scatterChart(props); return <div>{children}</div> },
  Scatter: (props: Record<string, unknown>) => { mocks.scatters(props); return <span>{String(props.name)}</span> },
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => <span>Chart legend</span>,
  LabelList: () => null,
}))

import { CancerGeneCensusChart } from "@/components/knowledgebase/CancerGeneCensusChart"
import { GeneCoverageChart } from "./GeneCoverageChart"
import { PanelAnalysisCapabilityChart } from "./PanelAnalysisCapabilityChart"
import { SampleCompositionCharts } from "./SampleCompositionCharts"
import { TierDistributionChart } from "./TierDistributionChart"
import { TopTieredGenesChart } from "./TopTieredGenesChart"

describe("dashboard charts", () => {
  beforeEach(() => vi.clearAllMocks())

  it("passes tier data to an exportable panel and cycles supplied colors", () => {
    const data = [{ name: "Tier 1", value: 4 }, { name: "Tier 2", value: 2 }, { name: "Tier 3", value: 1 }]
    render(<TierDistributionChart data={data} colors={["red", "blue"]} />)

    expect(screen.getByRole("region", { name: "Tier distribution" })).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tier_distribution",
      data,
    }))
    expect(mocks.cells.mock.calls.map(([props]) => props.fill)).toEqual(["red", "blue", "red"])
    expect(screen.getByText("Chart legend")).toBeVisible()
  })

  it("renders three census rings and ranked supporting context", () => {
    render(<CancerGeneCensusChart data={{
      available: true,
      total_genes: 3,
      tiers: [{ name: "Tier 1", value: 2 }, { name: "Tier 2", value: 1 }],
      origins: [{ name: "Somatic only", value: 2 }, { name: "Germline only", value: 1 }],
      roles: [{ name: "Tumour suppressor", value: 2 }, { name: "Oncogene", value: 1 }],
      mutation_types: [{ name: "Missense", value: 2 }],
      molecular_genetics: [{ name: "Dominant", value: 1 }],
      hallmarks: [{ name: "Genome instability", value: 1 }],
      hallmark_records: 1,
    }} />)

    expect(screen.getByRole("img", { name: /cancer gene census summary for 3 genes/i })).toBeVisible()
    expect(screen.getByText("Inner ring - CGC tier")).toBeVisible()
    expect(screen.getByText("Middle ring - origin scope")).toBeVisible()
    expect(screen.getByText("Outer ring - role in cancer")).toBeVisible()
    expect(screen.getByText("Mutation types")).toBeVisible()
    expect(screen.getByText("Hallmarks - 1 record")).toBeVisible()
    expect(mocks.pie).toHaveBeenCalledTimes(3)
  })

  it("renders covered and germline series from assay coverage data", () => {
    const data = [{ name: "Hematology", Covered: 385, Germline: 12 }]
    render(<GeneCoverageChart data={data} />)

    expect(screen.getByRole("region", { name: "Gene coverage per assay" })).toBeVisible()
    expect(screen.getByText("Covered genes")).toBeVisible()
    expect(screen.getByText("Germline genes")).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "gene_coverage_per_assay",
      data,
    }))
    expect(mocks.scatterChart).toHaveBeenCalledWith(expect.objectContaining({ layout: "vertical" }))
    expect(mocks.scatters).toHaveBeenNthCalledWith(1, expect.objectContaining({
      name: "Covered genes",
      data: [{ name: "Hematology", genes: 385 }],
    }))
    expect(mocks.scatters).toHaveBeenNthCalledWith(2, expect.objectContaining({
      name: "Germline genes",
      data: [{ name: "Hematology", genes: 12 }],
    }))
  })

  it("renders enabled and reportable panel capabilities as an exportable chart", () => {
    const data = [{ name: "SNV", Enabled: 3, Reportable: 2 }]
    render(<PanelAnalysisCapabilityChart data={data} />)

    expect(screen.getByRole("region", { name: "Panel analysis capability" })).toBeVisible()
    expect(screen.getByText("Reportable")).toBeVisible()
    expect(screen.getByText("Enabled, not reportable")).toBeVisible()
    expect(screen.getByText("2/3")).toBeVisible()
    expect(screen.getByText("67% reportable")).toBeVisible()
    expect(screen.getByText("1 enabled only")).toBeVisible()
    expect(screen.getByRole("img", { name: /SNV: 2 of 3 reportable, 67 percent/i })).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "panel_analysis_capability",
      data,
    }))
  })

  it("keeps eleven capability rings separated and shows zero results without a progress dot", () => {
    const data = Array.from({ length: 11 }, (_, index) => ({
      name: `Analysis ${index + 1}`, Enabled: 8, Reportable: index === 0 ? 0 : 8,
    }))
    const { container } = render(<PanelAnalysisCapabilityChart data={data} />)
    const tracks = [...container.querySelectorAll(".panel-capability-track")]
    expect(tracks).toHaveLength(11)
    tracks.forEach((track, index) => {
      expect(track).toHaveAttribute("stroke", "var(--chart-track)")
      if (!index) return
      const previous = tracks[index - 1]
      const separation = Number(track.getAttribute("cx")) - Number(previous.getAttribute("cx"))
      const diameters = Number(track.getAttribute("r")) + Number(previous.getAttribute("r"))
      expect(separation - diameters).toBeGreaterThan(15)
    })
    expect(container.querySelectorAll(".panel-capability-progress")).toHaveLength(10)
    expect(tracks[0].parentElement!.querySelector(".panel-capability-progress")).toBeNull()
    expect(screen.getByText("0/8")).toBeVisible()
  })

  it("shows composition counts and percentages with an accessible pipeline summary", () => {
    render(
      <SampleCompositionCharts
        groups={[
          { name: "Omics", rows: [{ name: "dna", value: 8 }, { name: "rna", value: 2 }] },
          { name: "Pairing", rows: [] },
        ]}
        pipelines={[
          { name: "SomaticPanelPipeline", version: "3.2.0", count: 8, analysed: 6 },
        ]}
        colors={["red", "blue"]}
      />,
    )

    expect(screen.getByText("Omics")).toBeVisible()
    expect(screen.getByText("Pairing")).toBeVisible()
    expect(screen.getByText("No data")).toBeVisible()
    expect(screen.getByText("Pipeline throughput")).toBeVisible()
    expect(screen.getAllByText("Analysed")[0]).toBeVisible()
    expect(screen.getAllByText("Awaiting review")[0]).toBeVisible()
    expect(screen.getByRole("img", { name: "Omics: dna 8 of 10, rna 2 of 10" })).toBeVisible()
    expect(screen.getByText("80%")).toBeVisible()
    expect(screen.getByText("20%")).toBeVisible()
    expect(screen.getByText("6 analysed · 2 awaiting review")).toBeVisible()
    expect(screen.getByText("75% complete")).toBeVisible()
    expect(screen.getByText("Shared count scale: 0–8 samples")).toBeVisible()
  })

  it("bounds completion to the sample count and retains every pipeline in the grouped total", () => {
    render(<SampleCompositionCharts groups={[]} colors={["red"]} pipelines={[
      { name: "Complete pipeline", count: 12, analysed: 20 },
      ...Array.from({ length: 9 }, (_, index) => ({ name: `Pipeline ${index}`, count: 1, analysed: -1 })),
    ]} />)

    expect(screen.getByRole("img", { name: /Complete pipeline \(unversioned\): 12 analysed, 0 awaiting review/ })).toBeVisible()
    expect(screen.getByText("2 other versions")).toBeVisible()
    expect(screen.getByText("0 analysed · 2 awaiting review")).toBeVisible()
    expect(screen.getByText("100% complete")).toBeVisible()
    expect(screen.getByText("Shared count scale: 0–12 samples")).toBeVisible()
  })

  it("renders top tiered genes as ranked proportional tier graphics", () => {
    render(
      <MemoryRouter>
        <TopTieredGenesChart
          data={[
            { gene: "TP53", total: 12, tier1: 7, tier2: 4, tier3: 1, nomenclatures: ["p", "g"] },
            { gene: "JAK2", total: 6, tier1: 5, tier2: 1, nomenclatures: ["p"] },
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole("list", { name: "Top tiered genes ranked by unique classified findings" })).toBeVisible()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
    expect(screen.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/variants/gene-cohort?gene=TP53")
    expect(screen.getByLabelText(/TP53, 12 unique findings/i)).toBeVisible()
    expect(screen.getAllByText("Protein (p)")).toHaveLength(2)
    expect(screen.getByText("Genomic (g)")).toBeVisible()
    expect(screen.getAllByText("T1")).toHaveLength(2)
    expect(screen.getByLabelText("Tier legend")).toHaveTextContent("Tier 4")
  })
})
