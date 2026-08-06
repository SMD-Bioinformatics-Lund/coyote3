import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), table: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    return <div>Results: {(props.data as unknown[]).length}</div>
  },
}))

import { TieredVariantSearch } from "./TieredVariantSearch"

function mount(route = "/variants/search") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}><TieredVariantSearch /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const response = {
  docs: [{ _id: "A1", gene: "TP53", tier: 1 }],
  assay_choices: ["hematology", "solid"],
  tier_stats: {
    total: { tier1: 10, tier2: 3, tier3: 2, tier4: 1 },
    by_assay: {
      hematology: { tier1: 8, tier2: 2, tier3: 1, tier4: 1 },
      solid: { tier1: 2, tier2: 1, tier3: 1, tier4: 0 },
    },
  },
}

describe("TieredVariantSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: response })
  })

  it("hydrates search mode and assay filters from the URL", async () => {
    mount("/variants/search?search_str=TP53&search_mode=gene&assays=hematology&include_annotation_text=true")

    expect(await screen.findByDisplayValue("TP53")).toBeVisible()
    await screen.findByText("Results: 1")
    expect(screen.getByRole("combobox")).toHaveValue("gene")
    expect(screen.getByLabelText("Include annotation text")).toBeChecked()
    expect(screen.getByRole("checkbox", { name: "hematology" })).toBeChecked()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining("search_str=TP53")))
    expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining("assays=hematology"))
  })

  it("applies trimmed search criteria and selected assays only on submit", async () => {
    mount()
    await screen.findByText("Results: 1")
    fireEvent.change(screen.getByPlaceholderText("Search gene, variant, annotation..."), { target: { value: "  BRAF  " } })
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "hgvsp" } })
    fireEvent.click(screen.getByLabelText("solid"))
    fireEvent.click(screen.getByRole("button", { name: "Search" }))

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.stringMatching(
      /search_str=BRAF.*search_mode=hgvsp.*assays=solid/,
    )))
  })

  it("renders tier totals and a compact expandable assay table", async () => {
    mount()
    await screen.findByText("Results: 1")
    expect(screen.getByText("Assay distribution")).toBeVisible()
    const details = screen.getByText("Assay distribution").closest("details")
    expect(details).not.toHaveAttribute("open")
    expect(within(details as HTMLElement).getByRole("columnheader", { name: "Tier 1" })).toBeInTheDocument()
    expect(within(details as HTMLElement).getByRole("rowheader", { name: "hematology" })).toBeInTheDocument()
  })

  it("clears all criteria and returns to variant mode", async () => {
    mount("/variants/search?search_str=TP53&search_mode=gene&assays=hematology&include_annotation_text=true")
    await screen.findByDisplayValue("TP53")
    await screen.findByText("Results: 1")
    fireEvent.click(screen.getByRole("button", { name: "Clear" }))

    expect(screen.getByPlaceholderText("Search gene, variant, annotation...")).toHaveValue("")
    expect(screen.getByRole("combobox")).toHaveValue("variant")
    expect(screen.getByLabelText("Include annotation text")).not.toBeChecked()
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "hematology" })).not.toBeChecked())
  })

  it("renders an empty result without assay or tier summaries", async () => {
    mocks.get.mockResolvedValueOnce({ data: { docs: [], assay_choices: [], tier_stats: {} } })
    mount()

    expect(await screen.findByText("Results: 0")).toBeVisible()
    expect(screen.queryByText("Assay distribution")).not.toBeInTheDocument()
    expect(screen.queryByText("Tier 1")).not.toBeInTheDocument()
  })

  it("shows the request error instead of rendering stale results", async () => {
    mocks.get.mockRejectedValueOnce(new Error("Tier search is unavailable"))
    mount()

    expect(await screen.findByText("Tier search is unavailable")).toBeVisible()
    expect(screen.queryByText(/Results:/)).not.toBeInTheDocument()
  })
})
