import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { PublicCatalog } from "./PublicCatalogPage"
import type { CatalogNavigationNode, Discovery, Offering } from "./offering-types"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock("@/components/data-table/DataTable", () => ({
  DataTable: ({ data }: { data: { hgnc_symbol: string }[] }) => <div>{data.map((row) => row.hgnc_symbol).join(", ")}</div>,
}))

const panel: Offering = {
  offering_id: "breast-panel", title: "Hematology MPN panel", group_id: "hematology", group_label: "Hematology",
  diagnosis_id: "mpn", diagnosis_label: "MPN", modality: "dna", family: "panel-dna",
  assay_id: "solid_GMSv3", assay_label: "Solid GMSv3", description: "Validated targeted service",
  analysis: ["SNV", "CNV"], price: { amount: "100.00", currency: "EUR", kind: "fixed", conditions: "" },
  pricing_message: "Contact for pricing", turnaround: "14 days", input_material: ["DNA"],
  report_deliverables: ["PDF"], methodology: "Targeted sequencing", limitations: "Validated regions only",
  ordering_information: "Contact the center", gene_scopes: [{ list_id: "breast", label: "Breast genes",
    revision: 2, analysis: "SNV", genes: ["BRCA1"], excluded_gene_count: 1 }],
}

const node = (node_id: string, label: string, parent_id: string | null = null,
  overrides: Partial<CatalogNavigationNode> = {}): CatalogNavigationNode => ({
  node_id, parent_id, offering_id: null, label, title: label, description: "",
  subheading: "", input_material: [], sample_modes: [], analysis: [], turnaround: "",
  report_deliverables: [], clinical_indications: [], limitations: "", public_notes: "",
  methodology: "", ordering_information: "", ...overrides,
})
const publication: Discovery = {
  version: 3, header: "Genomic test catalog", description: "Published service introduction",
  offerings: [panel],
  navigation: [
    node("dna", "DNA", null, { description: "DNA overview" }),
    node("panels", "Panels", "dna", { description: "Panel overview" }),
    node("hematology", "Hematology", "panels", { description: "Parent hematology information" }),
    node("mpn", "MPN", "hematology", { offering_id: panel.offering_id }),
    node("rna", "RNA", null, { description: "RNA overview" }),
  ],
}

function show({ data = publication, preview = false, path = "/", failOnce = false }: {
  data?: Discovery; preview?: boolean; path?: string; failOnce?: boolean
} = {}) {
  vi.mocked(api.get).mockImplementation(async url => ({ data: String(url).includes("/asp/")
    ? { gene_details: [] } : data, status: 200 }))
  vi.mocked(api.post).mockResolvedValue({ data, status: 200 })
  if (failOnce) vi.mocked(api.get).mockRejectedValueOnce(new Error("Temporarily unavailable"))
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><PublicCatalog previewDocument={preview
      ? { header: "Preview", description: "", layout: { order: [] }, modalities: {} } : undefined} /></MemoryRouter>
  </QueryClientProvider>)
}
const browse = () => within(screen.getByRole("navigation", { name: "Test categories" }))
const mpnPath = `/?node=${encodeURIComponent(JSON.stringify(["dna", "panel-dna", "hematology", "mpn"]))}`
const hematologyPath = `/?node=${encodeURIComponent(JSON.stringify(["dna", "panel-dna", "hematology"]))}`
beforeEach(() => vi.clearAllMocks())

describe("Published catalog hierarchy", () => {
  it("keeps the introduction and modality pages brief without aggregating service details", async () => {
    const rna: Offering = { ...panel, offering_id: "rna", modality: "rna", family: "wts",
      description: "RNA assay internal service detail" }
    show({ data: { ...publication, offerings: [panel, rna], navigation: [...publication.navigation,
      node("rna-service", "RNA service", "rna", { offering_id: rna.offering_id }),
    ] } })
    const overview = await screen.findByRole("region", { name: "Catalog overview" })
    expect(within(overview).getByText("Published service introduction")).toBeVisible()
    expect(within(overview).getByText(/analysis of somatic alterations in cancer/)).toBeVisible()
    for (const modality of ["DNA", "RNA"]) {
      fireEvent.click(browse().getByRole("button", { name: modality }))
      const content = screen.getByRole("region", { name: "Catalog overview" })
      expect(within(content).getByText(`${modality} overview`)).toBeVisible()
      expect(within(content).getByText(/sequencing services/)).toBeVisible()
      expect(screen.queryByRole("region", { name: "Service information" })).not.toBeInTheDocument()
      for (const text of ["Price", "Turnaround (TAT)", "Platform", "14 days", panel.description, rna.description, panel.assay_label]) {
        expect(within(content).queryByText(text, { exact: true })).not.toBeInTheDocument()
      }
    }
  })

  it("keeps price, TAT, samples and reviewed gene counts in the service panel", async () => {
    show({ path: mpnPath })
    const information = await screen.findByRole("region", { name: "Service information" })
    for (const label of ["Price", "Turnaround (TAT)", "Sample types / input material", "Sample modes", "Available analyses", "Published covered genes"]) {
      expect(within(information).getByText(label)).toBeVisible()
    }
    expect(within(information).getByText(/100/)).toBeVisible()
    expect(within(information).getByText("14 days")).toBeVisible()
    expect(within(information).getByText("1 unique gene in the published scope")).toBeVisible()
    expect(screen.queryByText("Service pricing:")).not.toBeInTheDocument()
    expect(screen.queryByRole("navigation", { name: "Entries in this section" })).not.toBeInTheDocument()
  })

  it("uses the immediate parent's missing service fields while retaining diagnosis overrides", async () => {
    const data: Discovery = { ...publication,
      offerings: [{ ...panel, description: "", turnaround: "", input_material: [], price: null }],
      navigation: publication.navigation.map(value => value.node_id === "hematology" ? {
        ...value, description: "Parent service wording", turnaround: "21 days", input_material: ["Bone marrow"],
        sample_modes: ["Tumor-normal"], price: { amount: "450.00", currency: "SEK", kind: "fixed", conditions: "" },
      } : value.node_id === "mpn" ? { ...value, description: "", turnaround: "", input_material: [] } : value),
    }
    show({ data, path: mpnPath })
    const information = await screen.findByRole("region", { name: "Service information" })
    expect(within(information).getByText("Parent service wording")).toBeVisible()
    expect(within(information).getByText("21 days")).toBeVisible()
    expect(within(information).getByText("Bone marrow")).toBeVisible()
    expect(within(information).getByText("Tumor-normal")).toBeVisible()
    expect(within(information).getByText(/450/)).toBeVisible()
    expect(within(information).getByText("SNV")).toBeVisible()
  })

  it("shows configured parent defaults and lets diagnosis-specific TAT and pricing override them", async () => {
    const data = { ...publication, navigation: publication.navigation.map(value => value.node_id === "hematology" ? {
      ...value, turnaround: "21 days", price: { amount: "450.00", currency: "SEK", kind: "fixed" as const, conditions: "" },
    } : value) }
    show({ data, path: hematologyPath })
    const information = await screen.findByRole("region", { name: "Service information" })
    expect(within(information).getByText("21 days")).toBeVisible()
    expect(within(information).getByText(/450/)).toBeVisible()
    fireEvent.click(browse().getByRole("button", { name: "MPN" }))
    const diagnosis = screen.getByRole("region", { name: "Service information" })
    expect(within(diagnosis).getByText("14 days")).toBeVisible()
    expect(within(diagnosis).queryByText("21 days")).not.toBeInTheDocument()
    expect(within(diagnosis).getByText(/100/)).toBeVisible()
    expect(within(diagnosis).queryByText(/450/)).not.toBeInTheDocument()
  })

  it("restores the method, group and diagnosis levels for flat published entries", async () => {
    const flat: Discovery = { ...publication, navigation: [
      node("dna", "DNA", null, { description: "DNA overview" }),
      node("raw-entry", "demo-hematology_gmsv1 (synthetic) / MPN", "dna", {
        offering_id: panel.offering_id, description: "MPN clinical service",
      }),
    ] }
    show({ data: flat })
    await screen.findByText("Published service introduction")
    expect(browse().getByRole("button", { name: "Panels" })).toBeVisible()
    expect(browse().queryByRole("button", { name: /demo-hematology/ })).not.toBeInTheDocument()
    fireEvent.click(browse().getByRole("button", { name: "Panels" }))
    fireEvent.click(browse().getByRole("button", { name: "Hematology" }))
    expect(screen.getByRole("heading", { name: "Hematology" })).toBeVisible()
    expect(screen.getByText("14 days")).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Clinical gene scope" })).not.toBeInTheDocument()
    fireEvent.click(browse().getByRole("button", { name: "MPN" }))
    expect(screen.getByRole("heading", { name: "MPN" })).toBeVisible()
    expect(screen.getByText("Validated targeted service")).toBeVisible()
    expect(screen.getByRole("navigation", { name: "Catalog location" })).toHaveTextContent("DNA/Panels/Hematology/MPN")
  })

  it("shows only exact branch matches when a diagnosis has several assays", async () => {
    const second = { ...panel, offering_id: "second-panel", title: "Second MPN panel", description: "Second exact match" }
    const otherMethod = { ...panel, offering_id: "wgs", family: "wgs", description: "Other method" }
    const otherGroup = { ...panel, offering_id: "other-group", group_id: "myeloid", group_label: "Myeloid", description: "Other group" }
    const otherDiagnosis = { ...panel, offering_id: "cll", diagnosis_id: "cll", diagnosis_label: "CLL", description: "Other diagnosis" }
    const otherModality: Offering = { ...panel, offering_id: "rna-mpn", modality: "rna", family: "panel-rna", description: "Other modality" }
    const items = [panel, second, otherMethod, otherGroup, otherDiagnosis, otherModality]
    const data: Discovery = { ...publication, offerings: items,
      navigation: [node("dna", "DNA"), node("rna", "RNA"), ...items
        .map(item => node(item.offering_id, item.title, item.modality, { offering_id: item.offering_id }))] }
    show({ data, path: mpnPath })
    expect(await screen.findByText("Validated targeted service")).toBeVisible()
    expect(screen.getByText("Second exact match")).toBeVisible()
    expect(screen.getAllByRole("article")).toHaveLength(2)
    for (const text of ["Other method", "Other group", "Other diagnosis", "Other modality"]) {
      expect(screen.queryByText(text)).not.toBeInTheDocument()
    }
    expect(screen.getByRole("heading", { name: "MPN", level: 2 })).toBeVisible()
    fireEvent.click(browse().getByRole("button", { name: "Hematology" }))
    expect(screen.queryAllByRole("article")).toHaveLength(0)
    expect(screen.getByRole("heading", { name: "Hematology" })).toBeVisible()
  })

  it("shows the selected level directly and keeps parent information separate", async () => {
    show()
    await screen.findByText("Published service introduction")
    fireEvent.click(browse().getByRole("button", { name: "DNA" }))
    expect(screen.getByText("DNA overview")).toBeVisible()
    fireEvent.click(browse().getByRole("button", { name: "Panels" }))
    expect(screen.getByText("Panel overview")).toBeVisible()
    fireEvent.click(browse().getByRole("button", { name: "Hematology" }))
    expect(screen.getByText("Parent hematology information")).toBeVisible()
    expect(screen.getByText("14 days")).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Clinical gene scope" })).not.toBeInTheDocument()
    fireEvent.click(browse().getByRole("button", { name: "MPN" }))
    expect(screen.getByRole("heading", { name: "MPN" })).toBeVisible()
    expect(screen.getByText("Validated targeted service")).toBeVisible()
    expect(screen.getByText("Targeted sequencing")).toBeVisible()
    expect(screen.getByText("Contact the center")).toBeVisible()
    expect(screen.getByText("BRCA1")).toBeVisible()
    const service = screen.getByRole("region", { name: "Service information" })
    const genes = screen.getByRole("heading", { name: "Clinical gene scope" })
    expect(service.compareDocumentPosition(genes) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    fireEvent.click(browse().getByRole("button", { name: "Hematology" }))
    expect(screen.getByText("Parent hematology information")).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Clinical gene scope" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "View details" })).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Requested genes")).not.toBeInTheDocument()
  })

  it("expands branches independently, preserves selection and supports keyboard tree controls", async () => {
    show({ path: mpnPath })
    await screen.findByRole("heading", { name: "MPN" })
    fireEvent.click(browse().getByRole("button", { name: "Collapse Panels" }))
    expect(browse().queryByRole("button", { name: "MPN" })).not.toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "MPN" })).toBeVisible()
    fireEvent.click(browse().getByRole("button", { name: "Expand Panels" }))
    expect(browse().getByRole("button", { name: "MPN" })).toHaveAttribute("aria-current", "page")
    fireEvent.click(browse().getByRole("button", { name: "DNA" }))
    expect(screen.getByText("DNA overview")).toBeVisible()
    expect(browse().getByRole("button", { name: "MPN" })).toBeVisible()
  })

  it("continues to open existing offering links with the hierarchy alongside", async () => {
    show({ path: "/?offering=breast-panel" })
    expect(await screen.findByRole("heading", { name: "MPN" })).toBeVisible()
    expect(browse().getByRole("button", { name: "MPN" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("navigation", { name: "Catalog location" })).toHaveTextContent("DNA/Panels/Hematology/MPN")
  })

  it.each(["/?node=withdrawn", "/?node=withdrawn&offering=breast-panel"])("reports unavailable selections without displaying another diagnosis: %s", async path => {
    show({ path })
    expect(await screen.findByText("This selection is not part of the current publication.")).toBeVisible()
    expect(screen.queryByText("Validated targeted service")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Browse available tests" }))
    expect(screen.getByText("Published service introduction")).toBeVisible()
  })

  it("gives the selected parent precedence over an offering left in the URL", async () => {
    show({ path: `${hematologyPath}&offering=breast-panel` })
    expect(await screen.findByText("Parent hematology information")).toBeVisible()
    expect(screen.getByRole("heading", { name: "Hematology" })).toBeVisible()
    expect(screen.queryByRole("heading", { name: "Clinical gene scope" })).not.toBeInTheDocument()
  })

  it("previews authenticated content and handles an empty publication", async () => {
    show({ data: { ...publication, offerings: [], navigation: [] }, preview: true })
    expect(await screen.findByRole("heading", { name: "No published services" })).toBeVisible()
    expect(api.post).toHaveBeenCalledWith("/admin/assay-catalog/preview/offerings", expect.objectContaining({ document: expect.any(Object) }), { errorNotice: "inline" })
  })

  it("allows retry after the publication fails to load", async () => {
    show({ failOnce: true })
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load published services.")
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("Published service introduction")).toBeVisible()
  })
})
