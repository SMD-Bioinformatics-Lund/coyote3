import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { PublicCatalog } from "./PublicCatalogPage"
import type { Offering } from "./offering-types"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: ({ data }: { data: { hgnc_symbol: string }[] }) => <div>{data.map((row) => row.hgnc_symbol).join(", ")}</div>,
}))

const panel: Offering = {
  offering_id: "breast-panel", title: "Breast panel", group_id: "solid", group_label: "Solid",
  diagnosis_id: "breast", diagnosis_label: "Breast", modality: "dna", family: "panel-dna",
  assay_id: "solid_GMSv3", assay_label: "Solid GMSv3", description: "Validated targeted service",
  analysis: ["SNV", "CNV"], price: { amount: "100.00", currency: "EUR", kind: "fixed", conditions: "" },
  pricing_message: "Contact for pricing", turnaround: "14 days", input_material: ["DNA"],
  report_deliverables: ["PDF"], methodology: "Targeted sequencing", limitations: "Validated regions only",
  ordering_information: "Contact the center", gene_scopes: [{ list_id: "breast", label: "Breast genes",
    revision: 2, analysis: "SNV", genes: ["BRCA1"], excluded_gene_count: 1 }],
}
const wgs: Offering = { ...panel, offering_id: "breast-wgs", title: "Breast WGS", family: "wgs",
  assay_id: "solid_wgs", assay_label: "Solid WGS", price: { ...panel.price!, amount: "400.00" },
  gene_scopes: [{ ...panel.gene_scopes[0], genes: ["TP53"], excluded_gene_count: 1 }],
}

function show(offerings = [panel, wgs], preview = false) {
  const data = { version: 3, header: "Genomic test catalog", description: "", offerings }
  vi.mocked(api.get).mockResolvedValue({ data, status: 200 })
  vi.mocked(api.post).mockResolvedValue({ data, status: 200 })
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><PublicCatalog previewDocument={preview ? { header: "Preview", description: "", layout: { order: [] }, modalities: {} } : undefined} /></MemoryRouter>
  </QueryClientProvider>)
}

describe("Published offering discovery", () => {
  it("uses diagnosis-first by default and preserves both services in assay-first mode", async () => {
    show([{ ...panel, assay_label: "SG3", assay_display_name: "Solid Tumor Panel GMS version 3" }, wgs])
    expect(await screen.findByText("2 available tests · publication 3")).toBeVisible()
    expect(screen.getByRole("button", { name: "By Diagnosis" })).toHaveAttribute("aria-pressed", "true")
    fireEvent.change(screen.getByLabelText("Diagnosis"), { target: { value: "breast" } })
    expect(screen.getAllByRole("article")).toHaveLength(2)
    fireEvent.click(screen.getByRole("button", { name: "By Assay" }))
    expect(screen.getByRole("option", { name: /^SG3$/ })).toBeVisible()
    expect(screen.getByText("Solid Tumor Panel GMS version 3")).toBeVisible()
    expect(screen.getByRole("heading", { name: "Solid Tumor Panel GMS version 3" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Breast panel" })).not.toBeInTheDocument()
    expect(screen.getAllByRole("article")).toHaveLength(2)
    fireEvent.change(screen.getByLabelText("Assay", { exact: true }), { target: { value: "solid_GMSv3" } })
    expect(screen.getAllByRole("article")).toHaveLength(1)
  })

  it("searches effective gene scopes without assuming WGS coverage", async () => {
    show()
    await screen.findByText("2 available tests · publication 3")
    fireEvent.change(screen.getByLabelText("Search diagnoses, genes and assays"), { target: { value: "BRCA1" } })
    expect(screen.getByRole("heading", { name: "Breast panel" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Breast WGS" })).not.toBeInTheDocument()
    expect(screen.getByText("Matched: Published gene scope")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "View details" }))
    expect(screen.getByText(/1 list genes outside validated assay coverage/)).toBeVisible()
    expect(screen.getByText("BRCA1")).toBeVisible()
  })

  it("compares independently priced offerings and capabilities", async () => {
    show()
    await screen.findByText("2 available tests · publication 3")
    fireEvent.click(screen.getByLabelText("Compare Breast panel"))
    fireEvent.click(screen.getByLabelText("Compare Breast WGS"))
    const table = screen.getByRole("table")
    expect(within(table).getByText(/100/)).toBeVisible()
    expect(within(table).getByText(/400/)).toBeVisible()
    const analysisRow = within(table).getByRole("rowheader", { name: "Analysis" }).closest("tr")!
    expect(within(analysisRow).getAllByText("SNV")).toHaveLength(2)
    expect(within(analysisRow).getAllByText("CNV")).toHaveLength(2)
    expect(screen.queryByRole("option", { name: "No diagnosis / General testing" })).not.toBeInTheDocument()
  })

  it("previews through the authenticated endpoint and handles no public services", async () => {
    show([], true)
    expect(await screen.findByRole("heading", { name: "No published services" })).toBeVisible()
    expect(api.post).toHaveBeenCalledWith("/admin/assay-catalog/preview/offerings", expect.objectContaining({ document: expect.any(Object) }))
  })
})
