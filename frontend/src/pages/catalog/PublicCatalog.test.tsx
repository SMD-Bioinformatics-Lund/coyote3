import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { PublicCatalogMatrix } from "./PublicCatalogMatrixPage"

beforeEach(() => localStorage.clear())

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: ({ data, columns }: { data: unknown[]; columns: unknown[] }) => (
    <div data-testid="gene-table">{data.length} genes, {columns.length} columns</div>
  ),
}))

vi.mock("@/components/knowledgebase/OncoKbGeneBadge", () => ({
  GeneWithOncoKbBadge: ({ displayGene }: { displayGene: string }) => <span>{displayGene}</span>,
  KnowledgebaseGeneTags: () => null,
}))

function renderPage(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const matrixPayload = {
  columns: [
    {
      mod: "dna",
      modality_label: "DNA",
      cat: "panel::hematology::hema_gmsv1::base",
      isgl_key: "myeloid",
      isgl_label: "Myeloid genes",
      analysis: "SNV",
    },
    {
      mod: "dna",
      modality_label: "DNA",
      cat: "panel::solid::solid_gmsv3::colon",
      isgl_key: "colon",
      isgl_label: "Colon genes",
      analysis: "CNV",
    },
  ],
  genes: ["TP53", "DNMT3A"],
  matrix: {
    TP53: {
      dna: {
        "panel::hematology::hema_gmsv1::base": { myeloid: true },
      },
    },
  },
  page: 1,
  per_page: 100,
  total: 125,
  has_next: true,
  has_previous: false,
}

describe("PublicCatalogMatrix", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.get).mockResolvedValue({ data: matrixPayload } as never)
  })

  it("identifies three assay columns independently when the same gene list is selected", async () => {
    const columns = ["HEM", "WGS", "MYELOID"].map(assay => ({ ...matrixPayload.columns[0],
      cat: `published-${assay}`, assay, diagnosis: "CLL", isgl_label: "CLL variants",
    }))
    vi.mocked(api.get).mockResolvedValue({ data: { ...matrixPayload, columns } } as never)
    renderPage(<PublicCatalogMatrix />)
    await screen.findByLabelText("Gene list")
    fireEvent.change(screen.getByLabelText("Gene list"), { target: { value: "CLL variants" } })
    for (const assay of ["HEM", "WGS", "MYELOID"]) {
      const header = screen.getByRole("columnheader", { name: `${assay} · CLL · SNV · CLL variants` })
      expect(header).toHaveTextContent("CLL")
      expect(within(screen.getByRole("row", { name: "Assays" })).getByRole("columnheader", { name: assay })).toBeVisible()
    }
    expect(screen.getByText("3 visible catalog column(s)")).toBeVisible()
  })

  it("renders grouped headers, coverage cells, and gene links", async () => {
    renderPage(<PublicCatalogMatrix />)

    expect(await screen.findByText("Assay Catalog - Gene Coverage Matrix")).toBeVisible()
    expect(screen.getByRole("columnheader", { name: "DNA" })).toBeVisible()
    expect(screen.getByRole("columnheader", { name: "hematology" })).toBeVisible()
    const analysis = screen.getByRole("combobox", { name: "Gene list type" })
    expect(analysis).toHaveValue("SNV")
    expect(within(analysis).queryByRole("option", { name: "All" })).not.toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "hema_gmsv1 · base · SNV · Myeloid genes" })).toHaveTextContent("Assay-wide")
    expect(within(screen.getByRole("row", { name: "Assays" })).getByRole("columnheader", { name: "hema_gmsv1" })).toBeVisible()
    expect(screen.queryByRole("columnheader", { name: /CNV · Colon genes/ })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/public/gene/TP53/info")
    expect(screen.getByText("Showing 2 of 125 gene(s) across 1 visible catalog column(s)")).toBeVisible()
  })

  it("keeps annotation visibility separate and remembers the matrix preference", async () => {
    localStorage.setItem("coyote3:catalog:annotations", "false")
    const view = renderPage(<PublicCatalogMatrix />)
    const toggle = await screen.findByRole("checkbox", { name: "Annotations" })
    expect(toggle).not.toBeChecked()
    expect(screen.queryByRole("columnheader", { name: "Annotations" })).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.getByRole("columnheader", { name: "Annotations" })).toBeVisible()
    expect(localStorage.getItem("coyote3:matrix:annotations")).toBe("true")
    expect(localStorage.getItem("coyote3:catalog:annotations")).toBe("false")
    view.unmount()
    renderPage(<PublicCatalogMatrix />)
    expect(await screen.findByRole("checkbox", { name: "Annotations" })).toBeChecked()
  })

  it("preserves editable sequencing headers and wraps labels without truncation", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: {
      ...matrixPayload,
      columns: matrixPayload.columns.map((column, index) => ({
        ...column,
        analysis: "SNV",
        mod: index === 0 ? "wgs" : "wts",
        modality_label: index === 0
          ? "Whole Genome Sequencing (WGS)"
          : "Whole Transcriptome Sequencing (WTS)",
        assay_group: "Hematology and Solid Tumors",
        isgl_label: "LongUnbrokenGeneListName",
      })),
    } } as never)
    renderPage(<PublicCatalogMatrix />)

    const wgs = await screen.findByRole("columnheader", { name: "Whole Genome Sequencing (WGS)" })
    expect(wgs).toHaveAttribute("title", "Whole Genome Sequencing (WGS)")
    expect(screen.getByRole("columnheader", { name: "Whole Transcriptome Sequencing (WTS)" })).toBeVisible()
    for (const header of screen.getAllByRole("columnheader")) {
      const label = header.querySelector("span")
      if (!label) continue
      expect(label).toHaveClass("whitespace-normal", "[overflow-wrap:anywhere]")
      expect(label).not.toHaveClass("truncate")
    }
  })

  it("filters visible columns without another server request", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: {
      ...matrixPayload,
      columns: matrixPayload.columns.map((column) => ({ ...column, analysis: "SNV" })),
    } } as never)
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("2 visible catalog column(s)")
    const callsBefore = vi.mocked(api.get).mock.calls.length

    fireEvent.change(screen.getByLabelText("Section"), { target: { value: "hematology" } })
    expect(screen.getByText("1 visible catalog column(s)")).toBeVisible()
    expect(vi.mocked(api.get).mock.calls).toHaveLength(callsBefore)
  })

  it("filters matrix analyses locally without additional requests", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("1 visible catalog column(s)")
    const calls = vi.mocked(api.get).mock.calls.length
    fireEvent.change(screen.getByLabelText("Gene list type"), { target: { value: "CNV" } })
    expect(screen.getByText("1 visible catalog column(s)")).toBeVisible()
    expect(screen.getByRole("columnheader", { name: "solid_gmsv3 · colon · CNV · Colon genes" })).toBeVisible()
    expect(screen.queryByRole("columnheader", { name: /SNV · Myeloid genes/ })).not.toBeInTheDocument()
    expect(vi.mocked(api.get).mock.calls).toHaveLength(calls)
  })

  it("removes all previous assay headers when changing analyses with repeated assay groups", async () => {
    const dna = ["A", "B", "A", "B"].map((assay, index) => ({
      ...matrixPayload.columns[0], assay: `DNA ${assay}`, assay_id: assay,
      cat: `panel::hematology::${assay}::diagnosis-${index}`, diagnosis: `Diagnosis ${index}`,
    }))
    const rna = ["C", "D"].map(assay => ({
      ...matrixPayload.columns[0], mod: "rna", modality_label: "RNA", analysis: "FUSION",
      assay: `RNA ${assay}`, assay_id: assay, cat: `rna::hematology::${assay}::base`,
    }))
    vi.mocked(api.get).mockResolvedValue({ data: { ...matrixPayload, columns: [...dna, ...rna] } } as never)
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("4 visible catalog column(s)")
    const headers = () => within(screen.getByRole("row", { name: "Assays" })).getAllByRole("columnheader")
    expect(headers()).toHaveLength(4)
    const calls = vi.mocked(api.get).mock.calls.length
    fireEvent.change(screen.getByLabelText("Gene list type"), { target: { value: "FUSION" } })
    expect(headers().map(header => header.textContent)).toEqual(["RNA C", "RNA D"])
    expect(screen.getByRole("columnheader", { name: "RNA" })).toHaveAttribute("colspan", "2")
    expect(screen.queryByRole("columnheader", { name: "DNA" })).not.toBeInTheDocument()
    for (const row of document.querySelectorAll(".catalog-matrix tbody tr")) {
      expect(row.querySelectorAll("td")).toHaveLength(2)
    }
    fireEvent.change(screen.getByLabelText("Gene list type"), { target: { value: "SNV" } })
    expect(headers().map(header => header.textContent)).toEqual(["DNA A", "DNA B", "DNA A", "DNA B"])
    expect(vi.mocked(api.get).mock.calls).toHaveLength(calls)
  })

  it("searches a gene on the server and resets pagination", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("1 visible catalog column(s)")
    fireEvent.change(screen.getByLabelText("Gene list type"), { target: { value: "CNV" } })

    fireEvent.change(screen.getByLabelText("Gene search"), { target: { value: " TP53 " } })
    fireEvent.submit(screen.getByRole("button", { name: "Search" }).closest("form")!)

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/public/assay-catalog-matrix/context?page=1&per_page=50&gene=TP53",
      )
    })
    expect((await screen.findAllByText(/1 visible catalog column\(s\) for "TP53"/))[0]).toBeVisible()
    expect(screen.getByLabelText("Gene list type")).toHaveValue("CNV")

    fireEvent.click(screen.getByRole("button", { name: "Clear" }))
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/public/assay-catalog-matrix/context?page=1&per_page=50")
    })
  })

  it("requests the next page and a changed page size", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("Page 1")

    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/public/assay-catalog-matrix/context?page=2&per_page=50")
    })

    fireEvent.change(await screen.findByLabelText("Rows"), { target: { value: "200" } })
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/public/assay-catalog-matrix/context?page=1&per_page=200")
    })
  })

  it("shows a useful matrix error", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("Matrix unavailable"))
    renderPage(<PublicCatalogMatrix />)
    expect(await screen.findByText("Matrix unavailable")).toBeVisible()
  })

  it("selects the available analysis when a catalog has no SNV columns", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: {
      ...matrixPayload,
      columns: [{ ...matrixPayload.columns[0], mod: "rna", analysis: "FUSION" }],
    } } as never)
    renderPage(<PublicCatalogMatrix />)
    expect(await screen.findByLabelText("Gene list type")).toHaveValue("FUSION")
    expect(screen.getByText("1 visible catalog column(s)")).toBeVisible()
  })
})
