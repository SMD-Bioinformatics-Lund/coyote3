import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ chartPanel: vi.fn(), bars: vi.fn(), bar: vi.fn(), cells: vi.fn(), tooltips: vi.fn() }))

vi.mock("@/components/plots/ChartPanel", () => ({
  ChartPanel: (props: Record<string, unknown>) => {
    mocks.chartPanel(props)
    return <section aria-label={String(props.title)}>{props.children as React.ReactNode}</section>
  },
}))

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.bars(props); return <div>{children}</div> },
  Bar: (props: { dataKey: string }) => { mocks.bar(props); return <span>{props.dataKey}</span> },
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: (props: Record<string, unknown>) => { mocks.cells(props); return <span /> },
  CartesianGrid: () => null,
  Legend: () => null,
  Tooltip: (props: Record<string, unknown>) => { mocks.tooltips(props); return null },
  XAxis: () => null,
  YAxis: () => null,
}))

import { GeneCohortCharts, PrevalenceTooltip } from "./GeneCohortCharts"

const props = {
  gene: "TP53",
  includeHistory: false,
  assays: [{
    asp_id: "solid_gmsv3",
    display_name: "Solid DNA GMSv3",
    asp_group: "solid",
    profiled_samples: 20,
    finding_samples: 5,
    prevalence_percent: 25,
  }],
  tierCounts: { "1": 2, "2": 3, "3": 1, "4": 0 },
  analysisTypeCounts: { SNV: 4, CNV: 1, FUSION: 1 },
  sexDistribution: [{ sex: "female", profiled_samples: 12, finding_samples: 3, prevalence_percent: 25 }],
    recurrentFindings: [{
    identity: "17_7675088_C_T",
    analysis_type: "SNV",
    hgvsp: "p.Arg175His",
    hgvsc: "c.524G>A",
    sample_count: 3,
    observation_count: 3,
    tiers: [1, 2],
  }],
}

describe("GeneCohortCharts", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders five exportable cohort plots with exact plotted data", () => {
    render(<GeneCohortCharts {...props} />)

    expect(screen.getByRole("region", { name: "Prevalence by assay" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Reported tier composition" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Prevalence by recorded sex" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Top recurrent findings" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Findings by analysis type" })).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_latest_reports_assay_prevalence",
      data: [expect.objectContaining({ assay_id: "solid_gmsv3", prevalence_percent: 25 })],
    }))
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_latest_reports_recurrent_findings",
      data: [expect.objectContaining({ finding: "17_7675088_C_T", analysis_type: "SNV", affected_samples: 3 })],
    }))
  })

  it("scopes export filenames to historical mode", () => {
    render(<GeneCohortCharts {...props} includeHistory />)
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_historical_reports_tier_distribution",
    }))
  })

  it("uses stable item-level hover without animated chart artifacts", () => {
    render(<GeneCohortCharts {...props} />)

    expect(mocks.tooltips).toHaveBeenCalledWith(expect.objectContaining({
      cursor: false,
      isAnimationActive: false,
      shared: false,
    }))
    expect(mocks.bar).toHaveBeenCalledWith(expect.objectContaining({
      activeBar: false,
      isAnimationActive: false,
    }))
  })

  it("renders prevalence tooltip values and the underlying sample fraction", () => {
    render(
      <PrevalenceTooltip
        active
        payload={[{
          graphicalItemId: "assay-prevalence",
          name: "Prevalence",
          value: 25,
          payload: { ...props.assays[0], assay: "Solid DNA GMSv3" },
        }]}
      />,
    )

    expect(screen.getByText("Solid DNA GMSv3")).toBeVisible()
    expect(screen.getByText("25.00% prevalence")).toBeVisible()
    expect(screen.getByText("5 finding samples / 20 profiled samples")).toBeVisible()
  })

  it("shows clear empty states while retaining exportable empty datasets", () => {
    render(<GeneCohortCharts {...props} assays={[]} sexDistribution={[]} recurrentFindings={[]} />)
    expect(screen.getByText("No assay prevalence is available.")).toBeVisible()
    expect(screen.getByText("No sex information is available.")).toBeVisible()
    expect(screen.getByText("No recurrent findings are available.")).toBeVisible()
  })
})
