import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))

import { RnaAnalysisTab } from "./RnaAnalysisTabs"

function renderTab(element: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{element}</QueryClientProvider>)
}

describe("RNA analysis tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({
      data: {
        expression: {
          sample: [
            { hgnc_symbol: "NCAM1", sample_expression: 521.79, reference_mean: 2.33, z: 63.84 },
            { hgnc_symbol: "CD19", sample_expression: 0.2, reference_mean: 100.33, z: -0.83 },
          ],
        },
        classification: {
          classifier_results: [
            { class: "ETV6-RUNX1", score: 0.12 },
            { class: "DUX4-high", score: 0.5 },
          ],
        },
      },
    })
  })

  it("renders expression and classification tables in a resizable combined view", async () => {
    renderTab(<RnaAnalysisTab sampleId="RNA_1" />)

    expect(await screen.findByText("NCAM1")).toBeVisible()
    expect(screen.getByText("521.79")).toBeVisible()
    expect(screen.getByLabelText("Z-score 63.84: Strong increase").parentElement).toHaveAttribute(
      "data-tooltip-context",
      "Expression z-score",
    )
    expect(screen.getByLabelText("Z-score -0.83: Reference-range decrease").parentElement).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("within the displayed reference range"),
    )
    expect(screen.getByText("DUX4-high")).toBeVisible()
    expect(screen.getByRole("progressbar", { name: "DUX4-high score" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    )
    expect(screen.getByText("ETV6-RUNX1")).toBeVisible()
    expect(screen.getByRole("separator", { name: "Resize expression and classification panes" })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledTimes(1)
    expect(mocks.get).toHaveBeenCalledWith("/samples/RNA_1/rna-analysis")
  })

  it("uses a full-width expression table when classification is unavailable", async () => {
    mocks.get.mockResolvedValueOnce({
      data: {
        expression: { sample: [{ hgnc_symbol: "CD19", sample_expression: 2.8, reference_mean: 10, z: -1.2 }] },
        classification: { classifier_results: [] },
      },
    })
    renderTab(<RnaAnalysisTab sampleId="RNA_EXPRESSION_ONLY" />)

    expect(await screen.findByText("CD19")).toBeVisible()
    expect(screen.queryByRole("separator")).not.toBeInTheDocument()
    expect(screen.getByText("1 genes")).toBeVisible()
  })
})
