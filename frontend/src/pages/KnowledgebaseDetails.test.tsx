import { screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { renderWithRouter } from "@/test/render"
import { KnowledgebaseDetails } from "./KnowledgebaseDetails"

const statusPayload = {
  releases: [
    {
      source: "cosmic_cancer_gene_census",
      release: "104",
      status: "active",
      records: 768,
      collections: [{ name: "cosmic_cancer_gene_census", records: 768 }],
    },
    { source: "civic", release: "2026-08", status: "active", records: 1200 },
  ],
  summary: { available_products: 2, total_records: 1968 },
}

const censusPayload = {
  available: true,
  total_genes: 768,
  tiers: [{ name: "Tier 1", value: 592 }, { name: "Tier 2", value: 176 }],
  origins: [{ name: "Somatic only", value: 657 }],
  roles: [{ name: "Tumour suppressor", value: 193 }],
  mutation_types: [],
  molecular_genetics: [],
  hallmarks: [],
  hallmark_records: 0,
}

const statisticsPayload = {
  sources: [{ key: "oncokb", name: "OncoKB", available: true, total: 42, unit: "genes", distribution: [], metrics: [] }],
}

vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    data: queryKey[0] === "knowledgebase-status"
      ? statusPayload
      : queryKey[0] === "knowledgebase-statistics"
        ? statisticsPayload
        : censusPayload,
    isLoading: false,
    error: null,
  }),
}))

vi.mock("@/components/dashboard/DashboardCharts", () => ({
  CancerGeneCensusChart: ({ data }: { data: typeof censusPayload }) => (
    <div>Census chart for {data.total_genes} genes</div>
  ),
  KnowledgebaseStatisticsCharts: () => <div>Knowledgebase source charts</div>,
}))

describe("Knowledgebase Details page", () => {
  it("shows grouped sources, product statistics, and available census content", async () => {
    renderWithRouter(<KnowledgebaseDetails />)

    expect(screen.getByRole("heading", { name: "Knowledgebase Details" })).toBeVisible()
    expect(screen.getByText("Knowledgebases online")).toBeVisible()
    expect(screen.getAllByText("COSMIC")).toHaveLength(2)
    expect(screen.getAllByText("CIViC")).toHaveLength(2)
    expect(screen.queryByRole("link", { name: /details/i })).not.toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Cancer Gene Census" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Reference coverage" })).toBeVisible()
    expect(screen.getByRole("heading", { name: "Installed products" })).toBeVisible()
  })
})
