import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { CatalogOfferingDetails } from "./CatalogOfferingDetails"
import type { Offering } from "./offering-types"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn() } }))

const offering: Offering = {
  offering_id: "synthetic-hema", title: "Synthetic hematology / MPN", group_id: "hematology",
  group_label: "Hematology", diagnosis_id: "mpn", diagnosis_label: "MPN", modality: "dna",
  family: "panel-dna", assay_id: "synthetic-hema", assay_label: "HEM demo", description: "Synthetic service",
  analysis: ["SNV", "CNV", "FUSION"], price: null, pricing_message: "Contact for pricing", turnaround: "5 days",
  input_material: ["DNA"], report_deliverables: ["PDF"], methodology: "Targeted sequencing",
  limitations: "Synthetic example", ordering_information: "Contact the center",
  gene_scopes: [
    { list_id: "snv-a", label: "SNV A", revision: 2, analysis: "SNV", genes: ["TP53"], excluded_gene_count: 0 },
    { list_id: "snv-b", label: "SNV B", revision: 1, analysis: "SNV", genes: ["TP53", "FLT3"], excluded_gene_count: 0 },
    { list_id: "cnv", label: "CNV genes", revision: 3, analysis: "CNV", genes: ["MYC"], excluded_gene_count: 0 },
  ],
}

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><CatalogOfferingDetails offering={offering} /></MemoryRouter>
  </QueryClientProvider>)
}

it("annotates only published genes, combines memberships and isolates each analysis", async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { gene_details: [
    { hgnc_symbol: "TP53", hgnc_id: "HGNC:11998", gene_name: "tumor protein p53", chromosome: "17",
      refseq_mane_plus_clinical: ["NM_000546.6"], ensembl_mane_select: "ENST00000269305.9" },
    { hgnc_symbol: "MYC", hgnc_id: "HGNC:7553", gene_name: "MYC proto-oncogene", chromosome: "8" },
    { hgnc_symbol: "OUTSIDE", gene_name: "Not in the published offering" },
  ] } })
  show()
  expect(await screen.findByText("tumor protein p53")).toBeVisible()
  expect(api.get).toHaveBeenCalledWith("/public/asp/synthetic-hema/genes")
  const panel = screen.getByRole("tabpanel")
  expect(within(panel).getAllByRole("link", { name: "TP53" })).toHaveLength(1)
  expect(within(panel).getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/public/gene/11998/info")
  expect(within(panel).getByRole("link", { name: "FLT3" })).toBeVisible()
  expect(within(panel).queryByText("Not in the published offering")).not.toBeInTheDocument()
  expect(within(panel).queryByRole("link", { name: "MYC" })).not.toBeInTheDocument()
  const tp53Row = within(panel).getByRole("link", { name: "TP53" }).closest("tr")!
  expect(within(tp53Row).getByText("SNV A")).toBeVisible()
  expect(within(tp53Row).getByText("SNV B")).toBeVisible()
  expect(within(tp53Row).getByText("NM_000546.6")).toBeVisible()
  expect(within(tp53Row).getByLabelText("RefSeq MANE Plus Clinical")).toHaveTextContent("RS MC+")
  expect(within(tp53Row).queryByText("ENST00000269305.9")).not.toBeInTheDocument()
  expect(within(panel).getByRole("columnheader", { name: /Transcript/ })).toBeVisible()
  expect(within(panel).queryByRole("columnheader", { name: /Ensembl gene ID/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("tab", { name: /CNV/ }))
  expect(within(screen.getByRole("tabpanel")).getByRole("link", { name: "MYC" })).toBeVisible()
  expect(within(screen.getByRole("tabpanel")).queryByRole("link", { name: "TP53" })).not.toBeInTheDocument()
  fireEvent.keyDown(screen.getByRole("tab", { name: /CNV/ }), { key: "ArrowRight" })
  expect(screen.getByRole("tab", { name: /Fusion/ })).toHaveFocus()
  expect(screen.getByRole("tab", { name: /Fusion/ })).toHaveAttribute("aria-selected", "true")
  expect(screen.getByText("No public gene list is published for FUSION.")).toBeVisible()
})

it("retains published symbols when HGNC reference information cannot be loaded", async () => {
  vi.mocked(api.get).mockRejectedValue(new Error("Reference unavailable"))
  show()
  expect(await screen.findByText(/HGNC reference information is unavailable/)).toBeVisible()
  const panel = screen.getByRole("tabpanel")
  expect(within(panel).getByRole("link", { name: "TP53" })).toBeVisible()
  expect(within(panel).getByRole("link", { name: "FLT3" })).toBeVisible()
})
