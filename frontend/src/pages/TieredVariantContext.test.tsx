import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({ get: vi.fn(), table: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.table(props)
    const rows = props.data as Record<string, any>[]
    const columns = props.columns as Record<string, any>[]
    return (
      <div data-testid="reported-matches">
        {rows.length} matches
        {rows.map((original, rowIndex) => (
          <div data-testid={`reported-row-${rowIndex}`} key={rowIndex}>
            {columns.map((column, columnIndex) => {
              const id = column.id || column.accessorKey || `column-${columnIndex}`
              const value = column.accessorFn
                ? column.accessorFn(original, rowIndex)
                : original[column.accessorKey]
              const row = {
                original,
                getValue: (requestedId: string) => {
                  const requested = columns.find((candidate) => (candidate.id || candidate.accessorKey) === requestedId)
                  return requested?.accessorFn
                    ? requested.accessorFn(original, rowIndex)
                    : original[requested?.accessorKey || requestedId]
                },
              }
              return (
                <div data-testid={`reported-cell-${rowIndex}-${id}`} key={id}>
                  {column.cell ? column.cell({ row }) : String(value ?? "")}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    )
  },
}))

import { TieredVariantContext } from "./TieredVariantContext"

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/variants/reported/VAR_1/2"]}>
        <Routes>
          <Route path="/variants/reported/:variantId/:tier" element={<TieredVariantContext />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("TieredVariantContext", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders normalized identity and passes all reported matches to the table", async () => {
    const docs = [
      {
        sample_name: "SAMPLE_A",
        sample_id: "OID_A",
        assay: "hema_gmsv1",
        subpanel: "hem",
        tier: 2,
        hgvsp: "p.Arg175His",
        hgvsc: "c.524G>A",
        report_id: "REPORT_1",
        report_num: 4,
        reported_on: "2026-08-01T10:00:00Z",
        var_oid: "VAR_OID_1",
      },
      { sample: { name: "SAMPLE_B" }, annotation: { assay: "solid_gmsv3" }, tier: 2, hgvsc: "c.524G>A" },
    ]
    mocks.get.mockResolvedValue({ data: {
      tier: 2,
      sample: { name: "SAMPLE_A" },
      variant: {
        SAMPLE_ID: "OID_A",
        simple_id: "17_7579472_G_A",
        simple_id_hash: "hash-1",
        INFO: { selected_CSQ: { SYMBOL: "TP53", HGVSc: "c.524G>A", HGVSp: "p.Arg175His" } },
      },
      docs,
    } })
    mount()

    expect(await screen.findByRole("heading", { name: "TP53 tier 2" })).toBeVisible()
    expect(screen.getByText("17_7579472_G_A")).toBeVisible()
    expect(screen.getByText("hash-1")).toBeVisible()
    expect(screen.getByTestId("reported-matches")).toHaveTextContent("2 matches")
    expect(screen.getByTestId("reported-cell-0-sample").querySelector("a")).toHaveAttribute("href", "/samples/SAMPLE_A")
    expect(screen.getByTestId("reported-cell-0-report").querySelector("a")).toHaveAttribute("href", "/samples/SAMPLE_A/reports/REPORT_1")
    expect(screen.getByTestId("reported-cell-0-actions").querySelector("a")).toHaveAttribute("href", "/samples/SAMPLE_A/variant/VAR_OID_1")
    expect(screen.getByTestId("reported-cell-0-hgvs")).toHaveTextContent("p.Arg175His")
    expect(screen.getByTestId("reported-cell-0-hgvs")).toHaveTextContent("c.524G>A")
    expect(screen.getByTestId("reported-cell-1-report")).toHaveTextContent("-")
    expect(screen.getByTestId("reported-cell-1-actions")).toHaveTextContent("-")
    expect(mocks.table).toHaveBeenCalledWith(expect.objectContaining({
      data: docs,
      totalCount: 2,
      filename: "reported_variant_matches.csv",
    }))
    expect(mocks.get).toHaveBeenCalledWith("/common/reported_variants/variant/VAR_1/2")
  })

  it("surfaces backend warnings without hiding results", async () => {
    mocks.get.mockResolvedValue({ data: {
      tier: 2,
      error: "Only historical matches were available.",
      variant: { INFO: { selected_CSQ: { SYMBOL: "TP53" } } },
      docs: [],
    } })
    mount()

    expect(await screen.findByText("Only historical matches were available.")).toBeVisible()
    expect(screen.getByTestId("reported-matches")).toHaveTextContent("0 matches")
  })

  it("renders a recoverable error when the API fails", async () => {
    mocks.get.mockRejectedValue(new Error("Variant context unavailable"))
    mount()

    expect(await screen.findByRole("heading", { name: "Unable to load tiered variant" })).toBeVisible()
    expect(screen.getByText("Variant context unavailable")).toBeVisible()
  })
})
