import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  chartPanel: vi.fn(),
  cells: vi.fn(),
  bars: vi.fn(),
  pie: vi.fn(),
  tooltips: vi.fn(),
  legend: vi.fn(),
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
  BarChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.bars(props); return <div>{children}</div> },
  Bar: ({ dataKey }: { dataKey: string }) => <span>{dataKey}</span>,
  ScatterChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.scatterChart(props); return <div>{children}</div> },
  Scatter: (props: Record<string, unknown>) => { mocks.scatters(props); return <span>{String(props.name)}</span> },
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: (props: Record<string, unknown>) => { mocks.tooltips(props); return null },
  Legend: (props: Record<string, unknown>) => { mocks.legend(props); return <span>Chart legend</span> },
  LabelList: () => null,
}))

import {
  GeneCoverageChart,
  PanelAnalysisCapabilityChart,
  SampleCompositionCharts,
  TierDistributionChart,
  TopTieredGenesChart,
} from "./DashboardCharts"

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
    expect(mocks.pie).toHaveBeenCalledWith(expect.objectContaining({
      startAngle: 90,
      endAngle: -270,
      innerRadius: "42%",
      outerRadius: "70%",
      isAnimationActive: true,
      animationDuration: 700,
    }))
    expect(mocks.legend).toHaveBeenCalledWith(expect.objectContaining({ verticalAlign: "bottom" }))
    expect(mocks.tooltips).toHaveBeenCalledWith(expect.objectContaining({ wrapperStyle: { zIndex: 40 } }))
    expect(screen.getByText("Chart legend")).toBeVisible()
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

  it("renders composition donuts and stacked pipeline throughput", () => {
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
    expect(mocks.pie).toHaveBeenCalledWith(expect.objectContaining({
      dataKey: "value",
      nameKey: "name",
      startAngle: 90,
      endAngle: -270,
      innerRadius: 36,
      outerRadius: 58,
      isAnimationActive: true,
      animationDuration: 700,
    }))
    expect(mocks.tooltips).toHaveBeenCalledWith(expect.objectContaining({ wrapperStyle: { zIndex: 40 } }))
    expect(mocks.bars).toHaveBeenCalledWith(expect.objectContaining({ layout: "vertical" }))
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
