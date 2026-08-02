import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api"
import { PublicCatalog, PublicCatalogMatrix } from "./PublicCatalog"

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn() },
}))

vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: ({ data, columns }: { data: unknown[]; columns: unknown[] }) => (
    <div data-testid="gene-table">{data.length} genes, {columns.length} columns</div>
  ),
}))

vi.mock("@/components/knowledgebase/OncoKbGeneBadge", () => ({
  GeneWithOncoKbBadge: ({ displayGene }: { displayGene: string }) => <span>{displayGene}</span>,
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

const catalogPayload = {
  order: ["dna"],
  modalities: {
    dna: {
      label: "DNA assays",
      description: "DNA catalog description",
      categories: {
        hematology: {
          label: "Hematology",
          gene_lists: [{ key: "myeloid", label: "Myeloid genes" }],
        },
      },
    },
  },
  right: {
    title: "Hematology GMSv1",
    subheading: "Clinical panel",
    description: "Panel description",
    catalog_id: "hema_catalog",
    asp_id: "hema_gmsv1",
    input_material: ["Blood"],
    tat: "21 days",
    sample_modes: ["Tumor-normal"],
    analysis: ["SNV", "CNV"],
    report_sections: ["Summary"],
    clinical_indications: ["Hematologic malignancy"],
    limitations: "Validated regions only",
    public_notes: "Public note",
    asp: { platform: "illumina", read_mode: "PE", read_length: 150 },
    custom_detail: "Center detail",
    gene_lists: [
      {
        key: "myeloid",
        label: "Myeloid genes",
        tat: "14 days",
        description: "Selected list details",
        analysis: ["SNV"],
        sample_modes: ["Tumor-normal"],
        input_material: ["Blood"],
        list_type: ["snv"],
      },
    ],
  },
  stats: { total: 2, covered_total: 2, germline_total: 1 },
  genes: [
    { display_symbol: "TP53", hgnc_id: "HGNC:11998", gene_name: "tumor protein p53" },
    { display_symbol: "DNMT3A", hgnc_id: "HGNC:2978", gene_name: "DNA methyltransferase 3 alpha" },
  ],
}

const matrixPayload = {
  columns: [
    {
      mod: "dna",
      modality_label: "DNA",
      cat: "panel::hematology::hema_gmsv1::base",
      isgl_key: "myeloid",
      isgl_label: "Myeloid genes",
    },
    {
      mod: "dna",
      modality_label: "DNA",
      cat: "panel::solid::solid_gmsv3::colon",
      isgl_key: "colon",
      isgl_label: "Colon genes",
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

describe("PublicCatalog", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
  })

  it("loads the catalog and narrows it by modality, category, and gene list", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: catalogPayload } as never)
    renderPage(<PublicCatalog />)

    expect(await screen.findByText("Hematology GMSv1")).toBeVisible()
    expect(screen.getByTestId("gene-table")).toHaveTextContent("2 genes, 3 columns")
    expect(screen.getByText("Public note")).toBeVisible()
    expect(screen.getByText("Center detail")).toBeVisible()

    fireEvent.click(screen.getByRole("button", { name: "DNA assays" }))
    expect(await screen.findByText("DNA catalog description")).toBeVisible()
    fireEvent.click(await screen.findByRole("button", { name: "Hematology" }))
    fireEvent.click(await screen.findByRole("button", { name: "Myeloid genes" }))

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/public/assay-catalog/context?mod=dna&cat=hematology&isgl_key=myeloid",
      )
    })
    expect(await screen.findByText("Selected gene list")).toBeVisible()
    expect(screen.getByText("Selected list details")).toBeVisible()
  })

  it("downloads the selected catalog as CSV", async () => {
    vi.mocked(api.get).mockImplementation(async (url: string) => {
      if (url.includes("genes.csv")) {
        return { data: { content: "gene\nTP53", filename: "myeloid.csv" } } as never
      }
      return { data: catalogPayload } as never
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    renderPage(<PublicCatalog />)

    fireEvent.click(await screen.findByRole("button", { name: "DNA assays" }))
    fireEvent.click(screen.getByRole("button", { name: "Catalog CSV" }))

    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/public/assay-catalog/genes.csv/context?mod=dna"))
    expect(click).toHaveBeenCalled()
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it("shows a useful catalog error", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("Catalog unavailable"))
    renderPage(<PublicCatalog />)
    expect(await screen.findByText("Catalog unavailable")).toBeVisible()
  })
})

describe("PublicCatalogMatrix", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.get).mockResolvedValue({ data: matrixPayload } as never)
  })

  it("renders grouped headers, coverage cells, and gene links", async () => {
    renderPage(<PublicCatalogMatrix />)

    expect(await screen.findByText("Assay Catalog - Gene Coverage Matrix")).toBeVisible()
    expect(screen.getByRole("columnheader", { name: "DNA" })).toBeVisible()
    expect(screen.getByRole("columnheader", { name: "hematology" })).toBeVisible()
    expect(screen.getByRole("link", { name: "TP53" })).toHaveAttribute("href", "/public/gene/TP53/info")
    expect(screen.getByText("Showing 2 of 125 gene(s) across 2 visible catalog column(s)")).toBeVisible()
  })

  it("filters visible columns without another server request", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("2 visible catalog column(s)")
    const callsBefore = vi.mocked(api.get).mock.calls.length

    fireEvent.change(screen.getByLabelText("Section"), { target: { value: "hematology" } })
    expect(screen.getByText("1 visible catalog column(s)")).toBeVisible()
    expect(vi.mocked(api.get).mock.calls).toHaveLength(callsBefore)
  })

  it("searches a gene on the server and resets pagination", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("2 visible catalog column(s)")

    fireEvent.change(screen.getByLabelText("Gene search"), { target: { value: " TP53 " } })
    fireEvent.submit(screen.getByRole("button", { name: "Search" }).closest("form")!)

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        "/public/assay-catalog-matrix/context?page=1&per_page=100&gene=TP53",
      )
    })
    expect((await screen.findAllByText(/2 visible catalog column\(s\) for "TP53"/))[0]).toBeVisible()

    fireEvent.click(screen.getByRole("button", { name: "Clear" }))
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/public/assay-catalog-matrix/context?page=1&per_page=100")
    })
  })

  it("requests the next page and a changed page size", async () => {
    renderPage(<PublicCatalogMatrix />)
    await screen.findByText("Page 1")

    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/public/assay-catalog-matrix/context?page=2&per_page=100")
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
})
