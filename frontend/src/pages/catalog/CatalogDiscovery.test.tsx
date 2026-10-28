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
  it("preserves assay filtering alongside the sidebar hierarchy", async () => {
    show([{ ...panel, assay_label: "SG3", assay_display_name: "Solid Tumor Panel GMS version 3" }, wgs])
    expect(await screen.findByText("2 available tests · publication 3")).toBeVisible()
    fireEvent.click(screen.getByText("Additional filters"))
    expect(screen.getByRole("option", { name: /^SG3$/ })).toBeVisible()
    expect(screen.getByText("Solid Tumor Panel GMS version 3")).toBeVisible()
    expect(screen.getByRole("heading", { name: "Solid Tumor Panel GMS version 3" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Breast panel" })).not.toBeInTheDocument()
    expect(screen.getAllByRole("article")).toHaveLength(2)
    fireEvent.change(screen.getByLabelText("Assay", { exact: true }), { target: { value: "solid_GMSv3" } })
    expect(screen.getAllByRole("article")).toHaveLength(1)
  })

  it("retains expanded branches and highlights the selected hierarchy without changing other scopes", async () => {
    const lung = { ...panel, offering_id: "lung", title: "Lung panel", diagnosis_id: "lung", diagnosis_label: "Lung" }
    const hema = { ...panel, offering_id: "hema", title: "Hematology panel", group_id: "hema", group_label: "Hematology", diagnosis_id: "breast", diagnosis_label: "Shared diagnosis" }
    const rna = { ...panel, offering_id: "rna", title: "RNA panel", modality: "rna" as const, family: "panel-rna" }
    show([panel, wgs, lung, hema, rna])
    await screen.findByText("5 available tests · publication 3")
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels" }))
    expect(screen.getAllByRole("article")).toHaveLength(3)
    const solid = screen.getByRole("button", { name: "DNA Panels / Solid" })
    expect(solid).toHaveTextContent("2")
    fireEvent.click(solid)
    expect(screen.getAllByRole("article")).toHaveLength(2)
    expect(screen.queryByRole("button", { name: "DNA Panels / Solid / Shared diagnosis" })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" }))
    expect(screen.getAllByRole("article")).toHaveLength(1)
    expect(screen.getByRole("heading", { name: "Breast panel" })).toBeVisible()
    for (const name of ["DNA", "DNA Panels", "DNA Panels / Solid"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("data-ancestor", "true")
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-pressed", "false")
    }
    expect(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" })).toHaveAttribute("aria-pressed", "true")
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" }))
    expect(screen.getAllByRole("article")).toHaveLength(1)
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels / Solid" }))
    expect(screen.getAllByRole("article")).toHaveLength(2)
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels / Hematology" }))
    expect(screen.getAllByRole("article")).toHaveLength(1)
    expect(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" })).toBeVisible()
    expect(screen.getByRole("button", { name: "DNA Panels / Hematology / Shared diagnosis" })).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "RNA Panels" }))
    expect(screen.getAllByRole("article")).toHaveLength(1)
    expect(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" })).toBeVisible()
    expect(screen.getByRole("button", { name: "DNA" })).not.toHaveAttribute("data-ancestor")
    fireEvent.click(screen.getByRole("button", { name: "All tests" }))
    expect(screen.getAllByRole("article")).toHaveLength(5)
    fireEvent.click(screen.getByRole("button", { name: "Collapse DNA Panels" }))
    expect(screen.queryByRole("button", { name: "DNA Panels / Solid" })).not.toBeInTheDocument()
    expect(screen.getAllByRole("article")).toHaveLength(5)
    fireEvent.click(screen.getByRole("button", { name: "Expand DNA Panels" }))
    expect(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" })).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "DNA Panels / Solid / Breast" }))
    fireEvent.click(screen.getByRole("button", { name: "View details" }))
    fireEvent.click(await screen.findByRole("button", { name: "Back to available tests" }))
    expect(screen.getByRole("button", { name: "DNA Panels / Hematology / Shared diagnosis" })).toBeVisible()
    expect(screen.getByRole("button", { name: "Collapse RNA Panels" })).toBeVisible()
    expect(screen.getAllByRole("article")).toHaveLength(1)
    expect(screen.queryByRole("combobox", { name: "Biological group" })).not.toBeInTheDocument()
    expect(screen.queryByRole("combobox", { name: "Diagnosis" })).not.toBeInTheDocument()
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

  it("defaults to test-name ordering and filters with the DNA/RNA method sidebar", async () => {
    const rna = { ...panel, offering_id: "rna", title: "RNA test", modality: "rna" as const, family: "wts" }
    show([wgs, rna, panel])
    await screen.findByText("3 available tests · publication 3")
    expect(screen.getAllByRole("article").map(card => within(card).getByRole("heading").textContent))
      .toEqual(["Breast panel", "Breast WGS", "RNA test"])
    expect(screen.getByText("Additional filters").closest("details")).not.toHaveAttribute("open")
    fireEvent.click(screen.getByRole("button", { name: "DNA WGS" }))
    expect(screen.getAllByRole("article")).toHaveLength(1)
    expect(screen.getByRole("heading", { name: "Breast WGS" })).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "RNA WTS" }))
    expect(screen.getByRole("heading", { name: "RNA test" })).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "All tests" }))
    expect(screen.getAllByRole("article")).toHaveLength(3)
  })

  it("counts unique pasted genes and exposes unmatched symbols on cards and comparison", async () => {
    show()
    await screen.findByText("2 available tests · publication 3")
    fireEvent.change(screen.getByLabelText("Requested genes"), { target: { value: "brca1, TP53\nBRCA1\nNOTPUBLISHED" } })
    expect(screen.getAllByText("1 / 3 requested genes matched")).toHaveLength(2)
    fireEvent.click(screen.getAllByRole("button", { name: "View unmatched genes (2)" })[0])
    const dialog = await screen.findByRole("dialog")
    expect(within(dialog).getByText("NOTPUBLISHED")).toBeVisible()
    expect(within(dialog).queryByText("BRCA1")).not.toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }))
    fireEvent.click(screen.getByLabelText("Compare Breast panel"))
    fireEvent.click(screen.getByLabelText("Compare Breast WGS"))
    const table = screen.getByRole("table")
    expect(within(table).getAllByText("1 / 3 requested genes matched")).toHaveLength(2)
    expect(within(table).getAllByRole("button", { name: "View unmatched genes (2)" })).toHaveLength(2)
    fireEvent.change(screen.getByLabelText("Requested genes"), { target: { value: "NOTPUBLISHED" } })
    expect(screen.queryAllByRole("article")).toHaveLength(0)
    expect(screen.getByText(/No tests match the selected categories/)).toBeVisible()
  })
})
