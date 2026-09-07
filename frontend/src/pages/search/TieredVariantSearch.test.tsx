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

import { TieredFindingSamplesCell, TieredVariantSearch } from "./TieredVariantSearch"

function mount(route = "/variants/search") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}><TieredVariantSearch /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const response = {
  docs: [{
    _id: "A1",
    analysis_type: "FUSION",
    nomenclature: "f",
    genes: ["KMT2A", "AFF1"],
    gene1: "KMT2A",
    gene2: "AFF1",
    identity: "KMT2A::AFF1",
    variant: "KMT2A::AFF1",
    tier: 1,
  }],
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
    fireEvent.change(screen.getByPlaceholderText("Search gene, finding, annotation..."), { target: { value: "  BRAF  " } })
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "hgvsp" } })
    fireEvent.click(screen.getByLabelText("solid"))
    fireEvent.click(screen.getByRole("button", { name: "Search" }))

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.stringMatching(
      /search_str=BRAF.*search_mode=hgvsp.*assays=solid/,
    )))
  })

  it("normalizes exact gene searches before requesting results", async () => {
    mount()
    await screen.findByText("Results: 1")
    fireEvent.change(screen.getByPlaceholderText("Search gene, finding, annotation..."), { target: { value: " tp53 " } })
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "gene" } })
    fireEvent.click(screen.getByRole("button", { name: "Search" }))

    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining(
      "search_str=TP53&search_mode=gene",
    )))
    expect(screen.getByPlaceholderText("Search gene, finding, annotation...")).toHaveValue("TP53")
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

  it("provides nomenclature-specific columns for typed clinical findings", async () => {
    mount()
    await screen.findByText("Results: 1")

    const latestProps = mocks.table.mock.calls.at(-1)?.[0] as {
      columns: Array<{ id?: string; header?: string }>
      data: Array<Record<string, unknown>>
    }
    expect(latestProps.columns.map((column) => column.id)).toEqual(expect.arrayContaining([
      "analysis_type",
      "genes",
      "variant",
      "nomenclature",
      "genomic",
      "transcript",
      "assay_group",
      "subpanel",
      "samples",
    ]))
    expect(latestProps.data[0]).toMatchObject({
      analysis_type: "FUSION",
      nomenclature: "f",
      identity: "KMT2A::AFF1",
    })
  })

  it("renders descriptive nomenclature labels while retaining the stored codes", async () => {
    mount()
    await screen.findByText("Results: 1")

    expect(screen.getByRole("checkbox", { name: "Protein (p)" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "cDNA (c)" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Genomic (g)" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Copy number (cn)" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Fusion (f)" })).not.toBeChecked()
    expect(screen.getByRole("checkbox", { name: "Translocation (t)" })).not.toBeChecked()

    fireEvent.click(screen.getByRole("checkbox", { name: "Fusion (f)" }))
    fireEvent.click(screen.getByRole("button", { name: "Search" }))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.stringContaining("nomenclatures=f")))
  })

  it("shows five linked samples before expanding the remaining report references", () => {
    const samples = Object.fromEntries(Array.from({ length: 7 }, (_, index) => [
      `S${index + 1}`,
      { sample_name: `S${index + 1}`, latest_report_num: index + 1 },
    ]))
    render(
      <MemoryRouter>
        <TieredFindingSamplesCell samplesById={samples} />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole("link")).toHaveLength(5)
    expect(screen.getByRole("link", { name: "S1: 1" })).toHaveAttribute("href", "/samples/S1")
    fireEvent.click(screen.getByRole("button", { name: "Show 2 more" }))
    expect(screen.getAllByRole("link")).toHaveLength(7)
    expect(screen.getByRole("button", { name: "Show fewer" })).toBeVisible()
  })

  it("clears all criteria and returns to variant mode", async () => {
    mount("/variants/search?search_str=TP53&search_mode=gene&assays=hematology&include_annotation_text=true")
    await screen.findByDisplayValue("TP53")
    await screen.findByText("Results: 1")
    fireEvent.click(screen.getByRole("button", { name: "Clear" }))

    expect(screen.getByPlaceholderText("Search gene, finding, annotation...")).toHaveValue("")
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
