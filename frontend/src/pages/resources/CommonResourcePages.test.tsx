import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  delete: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock("@/lib/api", () => ({ api: { get: mocks.get, delete: mocks.delete } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: mocks.success, notifyActionError: mocks.error }))

import { CoverageBlacklistPage, GeneInfoPage, PublicAspGenesPage, PublicGenelistPage } from "./CommonResourcePages"

function renderRoute(path: string, route: string, page: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <Routes><Route path={route} element={page} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  }
}

describe("GeneInfoPage", () => {
  beforeEach(() => vi.clearAllMocks())

  it("renders normalized HGNC metadata, transcripts, references, and external links", async () => {
    mocks.get.mockResolvedValue({ data: { gene: {
      hgnc_symbol: "TP53", hgnc_id: "HGNC:11998", gene_name: "tumor protein p53", status: "Approved",
      aliases: ["P53", "BCC7"], previous_symbols: "TRP53", prev_name: ["old p53"], chromosome: "17",
      start: 7_661_779, end: 7_687_550, gene_gc_content: 47.126, locus: "protein-coding gene",
      locus_sortable: "17p13.1", ensembl_gene_id: "ENSG00000141510", entrez_id: "7157",
      refseq_mane_select: "NM_000546.6", ensembl_mane_select: "ENST00000269305.9",
      refseq_mane_plus_clinical: ["NM_001126112.3"], refseq_accession: "NM_000546.6;NM_001126112.3",
      omim_id: ["191170"], cosmic: "TP53", gene_type: ["tumor suppressor"], imgt: "TP53 reference",
      date_modified: "2026-08-01T10:00:00Z", pseudogene_org: ["chimpanzee"],
      additional_transcript_info: { "NM_000546.6": { start: 100, end: 900, length: 800, start_site: 120 } },
    } } })

    renderRoute("/genes/HGNC%3A11998", "/genes/:geneId", <GeneInfoPage />)

    expect(await screen.findByRole("heading", { name: "TP53", level: 1 })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/common/gene/HGNC:11998/info")
    expect(screen.getAllByText("tumor protein p53")).toHaveLength(2)
    expect(screen.getByText("P53")).toBeVisible()
    expect(screen.getAllByText("NM_001126112.3")).toHaveLength(2)
    expect(screen.getByRole("link", { name: /HGNC/i })).toHaveAttribute("href", expect.stringContaining("11998"))
    expect(screen.getByRole("link", { name: "191170" })).toHaveAttribute("href", expect.stringContaining("191170"))
    expect(screen.getByText("Additional Transcript Coordinates")).toBeVisible()
    expect(screen.getByText("chimpanzee")).toBeVisible()
  })

  it("renders empty-reference messages without inventing identifiers", async () => {
    mocks.get.mockResolvedValue({ data: { gene: { symbol: "GENE1", status: "Approved" } } })
    renderRoute("/genes/GENE1", "/genes/:geneId", <GeneInfoPage />)
    expect(await screen.findByText("No MANE select transcript recorded")).toBeVisible()
    expect(screen.getByText("No OMIM identifiers recorded")).toBeVisible()
    expect(screen.getByText("No COSMIC identifiers recorded")).toBeVisible()
  })

  it("shows a request error", async () => {
    mocks.get.mockRejectedValue(new Error("HGNC service unavailable"))
    renderRoute("/genes/TP53", "/genes/:geneId", <GeneInfoPage />)
    expect(await screen.findByText("HGNC service unavailable")).toBeVisible()
  })
})

describe("public gene resources", () => {
  beforeEach(() => vi.clearAllMocks())

  it("loads a selected gene list with the assay query and normalizes string rows", async () => {
    mocks.get.mockResolvedValue({ data: { title: "Myeloid genes", genes: ["FLT3", { gene: "NPM1", evidence: { source: "curated" } }] } })
    renderRoute("/public/genelists/myeloid?assay=hema_gmsv1", "/public/genelists/:genelistId", <PublicGenelistPage />)
    expect(await screen.findByRole("heading", { name: "Myeloid genes" })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/public/genelists/myeloid/view_context?assay=hema_gmsv1")
    expect(screen.getByText("FLT3")).toBeVisible()
    expect(screen.getByText("NPM1")).toBeVisible()
    expect(screen.getByText('{"source":"curated"}')).toBeVisible()
  })

  it("shows a public gene-list request error", async () => {
    mocks.get.mockRejectedValue(new Error("Gene list unavailable"))
    renderRoute("/public/genelists/missing", "/public/genelists/:genelistId", <PublicGenelistPage />)
    expect(await screen.findByText("Gene list unavailable")).toBeVisible()
  })

  it("renders only the selected assay context and its configured catalog lists", async () => {
    mocks.get.mockResolvedValue({ data: {
      asp: { display_name: "Hematology GMSv1", asp_category: "dna", platform: "illumina", read_mode: "paired-end" },
      catalog: {
        title: "GMS-HEM", description: "<strong>Targeted</strong> hematology assay.", modality_label: "DNA",
        family: "panel-dna", assay_group: "hematology", subpanel_id: "myeloid", input_material: ["DNA"],
        sample_modes: ["tumor-normal"], tat: "21 days", analysis: ["SNV", "CNV"], report_sections: ["Somatic"],
        clinical_indications: ["AML"], limitations: "Validated regions only", public_notes: "Clinical use",
        gene_lists: [{ key: "myeloid", label: "Myeloid", tat: "21 days", analysis: ["SNV"], sample_modes: ["tumor-normal"] }],
      },
      stats: { covered_total: 2, germline_total: 1 },
      genes: ["FLT3", { hgnc_symbol: "NPM1", hgnc_id: "HGNC:7910" }],
    } })
    renderRoute("/public/asp/hema_gmsv1/genes", "/public/asp/:aspId/genes", <PublicAspGenesPage />)

    expect(await screen.findByRole("heading", { name: "GMS-HEM", level: 1 })).toBeVisible()
    expect(mocks.get).toHaveBeenCalledWith("/public/asp/hema_gmsv1/genes")
    expect(screen.getByText("Targeted hematology assay.")).toBeVisible()
    expect(screen.getAllByText("myeloid").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("Validated regions only")).toBeVisible()
    expect(screen.getByText("Catalog Gene Lists")).toBeVisible()
    expect(screen.getByText("FLT3")).toBeVisible()
    expect(screen.getByText("NPM1")).toBeVisible()
  })
})

describe("CoverageBlacklistPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.delete.mockResolvedValue({ data: { status: "ok" } })
  })

  it("flattens gene regions and removes a selected blacklist entry", async () => {
    const user = userEvent.setup()
    mocks.get.mockResolvedValue({ data: { blacklisted: {
      TP53: { regions: [{ _id: "R1", region: "17:100-200", reason: "low coverage" }] },
      BRCA1: { _id: "R2", coord: "17:300-400", reason: "repetitive" },
    } } })
    const { client } = renderRoute("/coverage/blacklisted/hematology", "/coverage/blacklisted/:group", <CoverageBlacklistPage />)
    const invalidate = vi.spyOn(client, "invalidateQueries")

    expect(await screen.findByText("17:100-200")).toBeVisible()
    expect(screen.getByText("17:300-400")).toBeVisible()
    await user.click(screen.getAllByRole("button", { name: "Remove" })[0])

    await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith("/coverage/blacklist/entries/R1"))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["coverage-blacklisted", "hematology"] })
    expect(mocks.success).toHaveBeenCalledWith("Blacklist entry removed", expect.any(String), "Coverage")
  })

  it("reports removal failures through the notification system", async () => {
    const user = userEvent.setup()
    mocks.get.mockResolvedValue({ data: { blacklisted: { TP53: { _id: "R1", region: "17:100-200" } } } })
    const failure = new Error("Delete denied")
    mocks.delete.mockRejectedValue(failure)
    renderRoute("/coverage/blacklisted/solid", "/coverage/blacklisted/:group", <CoverageBlacklistPage />)
    await user.click(await screen.findByRole("button", { name: "Remove" }))
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Unable to remove blacklist entry", failure, "Coverage"))
  })
})
