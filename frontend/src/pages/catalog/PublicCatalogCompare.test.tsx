import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { PublicCatalogCompare } from "./PublicCatalogComparePage"
import type { Offering } from "./offering-types"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
const service = (name: string, amount: string): Offering => ({
  offering_id: name, title: name, assay_id: name, assay_label: `Assay ${name}`,
  group_id: "hema", group_label: "Hematology", diagnosis_id: "mpn", diagnosis_label: "MPN",
  modality: "dna", family: "panel-dna", description: `Service ${name}`, analysis: ["SNV"],
  price: { amount, currency: "SEK", kind: "fixed", conditions: "" }, pricing_message: "",
  turnaround: "14 days", input_material: ["Bone marrow"], sample_modes: ["Tumor-normal"],
  platform: "Synthetic sequencer", read_length: 150, report_deliverables: ["PDF"],
  methodology: "Targeted sequencing", limitations: "Validated scope", ordering_information: "Contact the center",
  gene_scopes: [{ list_id: "genes", label: "MPN genes", revision: 1, analysis: "SNV", genes: ["TP53"], excluded_gene_count: 0 }],
})
function show(path = "/public/catalog/compare", preview = false) {
  const data = { version: 1, header: "Synthetic catalog", description: "", navigation: [],
    offerings: [service("A", "100"), service("B", "200"), service("C", "300"), service("D", "400")] }
  vi.mocked(api.get).mockResolvedValue({ data } as never)
  vi.mocked(api.post).mockResolvedValue({ data } as never)
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><PublicCatalogCompare previewDocument={preview ? {
      header: "Draft", description: "", layout: { order: [] }, modalities: {},
    } : undefined} /></MemoryRouter>
  </QueryClientProvider>)
}

it("compares exact reviewed services with aligned pricing, TAT and gene-scope rows", async () => {
  show("/public/catalog/compare?compare=A&compare=B")
  const table = await screen.findByRole("table", { name: "Published service comparison" })
  expect(within(table).getByRole("columnheader", { name: /Assay A/ })).toBeVisible()
  expect(within(table).getByRole("columnheader", { name: /Assay B/ })).toBeVisible()
  for (const name of ["Price", "Turnaround", "Sample types", "Sample modes", "Published covered genes", "Read length"]) {
    expect(within(table).getByRole("rowheader", { name })).toBeVisible()
  }
  expect(within(table).getAllByText("150 bp")).toHaveLength(2)
  fireEvent.change(screen.getByLabelText("Search assays to compare"), { target: { value: "Assay C" } })
  expect(within(table).getByRole("columnheader", { name: /Assay A/ })).toBeVisible()
  fireEvent.click(screen.getByRole("checkbox", { name: /Assay C/ }))
  expect(screen.getByRole("status")).toHaveTextContent("3 of 3 services selected")
  fireEvent.change(screen.getByLabelText("Search assays to compare"), { target: { value: "" } })
  expect(screen.getByRole("checkbox", { name: /Assay D/ })).toBeDisabled()
  fireEvent.click(screen.getByRole("checkbox", { name: /Assay B/ }))
  expect(screen.getByRole("checkbox", { name: /Assay D/ })).toBeEnabled()
})

it("previews comparisons through the authenticated endpoint without publishing", async () => {
  show("/admin/assay-catalog?version=draft-one", true)
  expect(await screen.findByText("Select at least two services for a comparison.")).toBeVisible()
  expect(api.post).toHaveBeenCalledWith("/admin/assay-catalog/preview/offerings", expect.objectContaining({ document: expect.any(Object) }), { errorNotice: "inline" })
})

it("does not count unpublished or removed offering IDs as comparison selections", async () => {
  show("/public/catalog/compare?compare=removed&compare=A")
  expect(await screen.findByText("1 of 3 services selected")).toBeVisible()
  expect(screen.getByRole("checkbox", { name: /Assay B/ })).toBeEnabled()
  expect(screen.queryByRole("table")).not.toBeInTheDocument()
})
