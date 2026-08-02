import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ chartPanel: vi.fn(), cells: vi.fn(), bars: vi.fn() }))
vi.mock("@/components/plots/ChartPanel", () => ({
  ChartPanel: (props: Record<string, unknown>) => {
    mocks.chartPanel(props)
    return <section aria-label={String(props.title)}>{props.children as React.ReactNode}</section>
  },
}))
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: (props: Record<string, unknown>) => { mocks.cells(props); return <span /> },
  BarChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.bars(props); return <div>{children}</div> },
  Bar: ({ dataKey }: { dataKey: string }) => <span>{dataKey}</span>,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}))

import { GeneCoverageChart, PanelAnalysisCapabilityChart, TierDistributionChart } from "./DashboardCharts"

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
  })

  it("renders covered and germline series from assay coverage data", () => {
    const data = [{ name: "Hematology", Covered: 385, Germline: 12 }]
    render(<GeneCoverageChart data={data} />)

    expect(screen.getByRole("region", { name: "Gene coverage per assay" })).toBeVisible()
    expect(screen.getByText("Covered")).toBeVisible()
    expect(screen.getByText("Germline")).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "gene_coverage_per_assay",
      data,
    }))
    expect(mocks.bars).toHaveBeenCalledWith(expect.objectContaining({ data }))
  })

  it("renders enabled and reportable panel capabilities as an exportable chart", () => {
    const data = [{ name: "SNV", Enabled: 3, Reportable: 2 }]
    render(<PanelAnalysisCapabilityChart data={data} />)

    expect(screen.getByRole("region", { name: "Panel analysis capability" })).toBeVisible()
    expect(screen.getByText("Enabled")).toBeVisible()
    expect(screen.getByText("Reportable")).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "panel_analysis_capability",
      data,
    }))
    expect(mocks.bars).toHaveBeenCalledWith(expect.objectContaining({ data }))
  })
})
