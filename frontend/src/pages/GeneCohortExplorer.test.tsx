import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))

import { GeneCohortExplorer } from "./GeneCohortExplorer"

function mount(route = "/variants/gene-cohort") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <GeneCohortExplorer />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const response = {
  query: { input: "TP53", resolved_symbol: "TP53" },
  gene: { hgnc_id: "HGNC:11998" },
  summary: {
    profiled_samples: 20,
    finding_samples: 5,
    prevalence_percent: 25,
    reported_observations: 7,
    unique_variants: 2,
  },
  denominator: {
    method: "sample_snv_isgl_then_asp_covered_genes",
    report_scope: "latest",
    ready_samples_considered: 24,
    samples_excluded_outside_gene_scope: 4,
    unrestricted_asp_scope_counts_as_profiled: true,
    duplicate_report_observations_removed: 0,
  },
  tier_counts: { "1": 2, "2": 3, "3": 2, "4": 0 },
  assays: [{
    asp_id: "solid_gmsv3",
    display_name: "Solid DNA GMSv3",
    asp_group: "solid",
    profiled_samples: 20,
    finding_samples: 5,
    prevalence_percent: 25,
  }],
  sex_distribution: [
    { sex: "female", profiled_samples: 12, finding_samples: 3, prevalence_percent: 25 },
    { sex: "male", profiled_samples: 8, finding_samples: 2, prevalence_percent: 25 },
  ],
  recurrent_variants: [{
    identity: "17_7675088_C_T",
    hgvsp: "p.Arg175His",
    hgvsc: "c.524G>A",
    sample_count: 3,
    observation_count: 3,
    tiers: [1, 2],
  }],
  samples: [{
    sample_name: "SAMPLE_1",
    asp_id: "solid_gmsv3",
    subpanel_id: "colon",
    environment: "production",
    sex: "female",
    tiers: [1],
    variants: ["p.Arg175His"],
  }],
  truncated: false,
}

describe("GeneCohortExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: response })
  })

  it("waits for a gene before requesting cohort data", () => {
    mount()
    expect(screen.getByRole("heading", { name: "Search for a gene" })).toBeVisible()
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it("submits a normalized gene and renders the access-scoped cohort", async () => {
    mount()
    fireEvent.change(screen.getByLabelText("Gene symbol or HGNC identifier"), {
      target: { value: " tp53 " },
    })
    fireEvent.click(screen.getByRole("button", { name: "Search" }))

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith("/common/gene/TP53/cohort-summary"))
    expect(await screen.findByRole("heading", { name: "TP53" })).toBeVisible()
    expect(screen.getByText("25.00%", { selector: "p" })).toBeVisible()
    expect(screen.getByText("Solid DNA GMSv3")).toBeVisible()
    expect(screen.getAllByText("p.Arg175His")).toHaveLength(2)
    expect(screen.getByRole("link", { name: "SAMPLE_1" })).toHaveAttribute("href", "/samples/SAMPLE_1")
  })

  it("shows a valid cohort with no reported mutation findings", async () => {
    mocks.get.mockResolvedValueOnce({
      data: { ...response, summary: { ...response.summary, finding_samples: 0 }, recurrent_variants: [], samples: [] },
    })
    mount("/variants/gene-cohort?gene=KRAS")

    expect(await screen.findByText("No reported mutations were found.")).toBeVisible()
    expect(screen.getByText("No samples have a reported finding for this gene.")).toBeVisible()
  })

  it("can include report history without double-counting a sample mutation", async () => {
    mocks.get.mockImplementation((url: string) => Promise.resolve({
      data: url.includes("include_history=true")
        ? {
            ...response,
            denominator: {
              ...response.denominator,
              report_scope: "historical",
              duplicate_report_observations_removed: 3,
            },
          }
        : response,
    }))
    mount("/variants/gene-cohort?gene=TP53")

    fireEvent.click(screen.getByRole("checkbox", { name: "Include historical reports" }))

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(
      "/common/gene/TP53/cohort-summary?include_history=true",
    ))
    expect(await screen.findByText("3 repeated report occurrence(s) were removed from the calculation.")).toBeVisible()
  })

  it("shows request failures", async () => {
    mocks.get.mockRejectedValueOnce(new Error("Gene cohort is unavailable"))
    mount("/variants/gene-cohort?gene=TP53")
    expect(await screen.findByText("Gene cohort is unavailable")).toBeVisible()
  })
})
