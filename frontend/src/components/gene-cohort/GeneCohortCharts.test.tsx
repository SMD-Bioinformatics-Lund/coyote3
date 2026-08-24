import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ chartPanel: vi.fn(), bars: vi.fn(), cells: vi.fn() }))

vi.mock("@/components/plots/ChartPanel", () => ({
  ChartPanel: (props: Record<string, unknown>) => {
    mocks.chartPanel(props)
    return <section aria-label={String(props.title)}>{props.children as React.ReactNode}</section>
  },
}))

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, ...props }: { children: React.ReactNode }) => { mocks.bars(props); return <div>{children}</div> },
  Bar: ({ dataKey }: { dataKey: string }) => <span>{dataKey}</span>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: (props: Record<string, unknown>) => { mocks.cells(props); return <span /> },
  CartesianGrid: () => null,
  Legend: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

import { GeneCohortCharts } from "./GeneCohortCharts"

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
  sexDistribution: [{ sex: "female", profiled_samples: 12, finding_samples: 3, prevalence_percent: 25 }],
  recurrentVariants: [{
    identity: "17_7675088_C_T",
    hgvsp: "p.Arg175His",
    hgvsc: "c.524G>A",
    sample_count: 3,
    observation_count: 3,
    tiers: [1, 2],
  }],
}

describe("GeneCohortCharts", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders four exportable cohort plots with exact plotted data", () => {
    render(<GeneCohortCharts {...props} />)

    expect(screen.getByRole("region", { name: "Prevalence by assay" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Reported tier composition" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Prevalence by recorded sex" })).toBeVisible()
    expect(screen.getByRole("region", { name: "Top recurrent mutations" })).toBeVisible()
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_latest_reports_assay_prevalence",
      data: [expect.objectContaining({ assay_id: "solid_gmsv3", prevalence_percent: 25 })],
    }))
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_latest_reports_recurrent_mutations",
      data: [expect.objectContaining({ mutation: "p.Arg175His", affected_samples: 3 })],
    }))
  })

  it("scopes export filenames to historical mode", () => {
    render(<GeneCohortCharts {...props} includeHistory />)
    expect(mocks.chartPanel).toHaveBeenCalledWith(expect.objectContaining({
      filename: "tp53_historical_reports_tier_distribution",
    }))
  })

  it("shows clear empty states while retaining exportable empty datasets", () => {
    render(<GeneCohortCharts {...props} assays={[]} sexDistribution={[]} recurrentVariants={[]} />)
    expect(screen.getByText("No assay prevalence is available.")).toBeVisible()
    expect(screen.getByText("No sex information is available.")).toBeVisible()
    expect(screen.getByText("No recurrent mutations are available.")).toBeVisible()
  })
})
