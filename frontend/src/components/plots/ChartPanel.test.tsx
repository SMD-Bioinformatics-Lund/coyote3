import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { exportChartAsPng, exportChartAsSvg, exportRowsAsCsv } from "@/lib/chart-export"
import { ChartPanel } from "./ChartPanel"

vi.mock("@/lib/chart-export", () => ({ exportChartAsPng: vi.fn(), exportChartAsSvg: vi.fn(), exportRowsAsCsv: vi.fn() }))

describe("ChartPanel", () => {
  it("renders context and exports each supported format with a sanitized filename", async () => {
    const user = userEvent.setup()
    const data = [{ assay: "hema", count: 3 }]
    render(<ChartPanel title="Gene coverage" description="Active definitions" filename="Gene coverage / assay" data={data}><svg aria-label="chart" /></ChartPanel>)

    expect(screen.getByText("Gene coverage")).toBeInTheDocument()
    expect(screen.getByText("Active definitions")).toBeInTheDocument()
    await user.click(screen.getByTitle("Export chart PNG"))
    await user.click(screen.getByTitle("Export chart SVG"))
    await user.click(screen.getByTitle("Export chart data CSV"))

    expect(exportChartAsPng).toHaveBeenCalledWith(expect.any(HTMLElement), "Gene_coverage_assay.png")
    expect(exportChartAsSvg).toHaveBeenCalledWith(expect.any(HTMLElement), "Gene_coverage_assay.svg")
    expect(exportRowsAsCsv).toHaveBeenCalledWith(data, "Gene_coverage_assay.csv")
  })
})
