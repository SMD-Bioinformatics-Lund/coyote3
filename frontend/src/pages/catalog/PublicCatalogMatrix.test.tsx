import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { PublicCatalogMatrix } from "./PublicCatalogMatrixPage"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }))

it("groups diagnosis columns beneath distinct assay identities and retains gene-list details", async () => {
  const columns = [
    { cat: "hem-mpn", assay_id: "hem-v1", assay: "HEM v1", diagnosis: "MPN" },
    { cat: "hem-cll", assay_id: "hem-v1", assay: "HEM v1", diagnosis: "CLL" },
    { cat: "wgs-mpn", assay_id: "hem-wgs", assay: "HEM WGS", diagnosis: "MPN" },
    // Two different assays may share a short name; they must remain separate groups.
    { cat: "other-mpn", assay_id: "hem-other", assay: "HEM WGS", diagnosis: "MPN" },
  ].map(column => ({ ...column, mod: "dna", assay_group: "Hematology",
    analysis: "SNV", isgl_key: "shared:SNV", isgl_label: "Shared gene list" }))
  vi.mocked(api.get).mockResolvedValue({ data: { columns, genes: [], total: 0 }, status: 200 })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><PublicCatalogMatrix /></MemoryRouter>
  </QueryClientProvider>)

  const assays = await screen.findByRole("row", { name: "Assays" })
  expect(within(assays).getAllByRole("columnheader")).toHaveLength(3)
  expect(within(assays).getByText("HEM v1").closest("th")).toHaveAttribute("colspan", "2")
  const diagnoses = screen.getByRole("row", { name: "Diagnoses / subpanels" })
  expect(within(diagnoses).getAllByRole("columnheader")).toHaveLength(4)
  expect(within(diagnoses).getByText("CLL")).toBeVisible()
  expect(within(diagnoses).queryByText("Shared gene list")).not.toBeInTheDocument()
  expect(within(diagnoses).getAllByRole("columnheader")[0]).toHaveAttribute(
    "aria-label", "HEM v1 · MPN · SNV · Shared gene list",
  )
  expect(screen.getByRole("columnheader", { name: "Gene" })).toHaveAttribute("rowspan", "4")

  fireEvent.change(screen.getByLabelText("Assay", { exact: true }), { target: { value: "HEM v1" } })
  expect(within(screen.getByRole("row", { name: "Assays" })).getAllByRole("columnheader")).toHaveLength(1)
  expect(within(screen.getByRole("row", { name: "Diagnoses / subpanels" })).getAllByRole("columnheader")).toHaveLength(2)
})
