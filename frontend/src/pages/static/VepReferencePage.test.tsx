import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import VepReferencePage from "./VepReferencePage"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))

const reference = (version: string) => ({ vep_id: version, source: "https://example.org/cache", vc_translation_source: "https://example.org/class", conseq_translation_source: "https://example.org/consequence",
  conseq_translations: { missense_variant: { short: "missense", desc: `Description for ${version}`, impact: "MODERATE", group: "missense", so_term: "SO:0001583" } }, consequence_groups: { missense: ["missense_variant"] }, variant_class_translations: {}, db_info: {}, consequence_diagram: null })

beforeEach(() => {
  mocks.get.mockReset()
  mocks.get.mockImplementation((url: string) => Promise.resolve({ data: url === "/public/vep" ? { versions: ["116", "103"] } : reference(url.split("/").pop() || "") }))
})

function mount(path = "/about/vep") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><VepReferencePage /></MemoryRouter></QueryClientProvider>)
}

it("selects the latest release and searches reference descriptions", async () => {
  mount()
  expect(await screen.findByText("Description for 116")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "SO:0001583" })).toHaveAttribute("href", "http://www.sequenceontology.org/miso/current_svn/term/SO:0001583")
  fireEvent.change(screen.getByLabelText("Search VEP terms"), { target: { value: "absent" } })
  expect(screen.getByText("No matching consequence terms.")).toBeInTheDocument()
})

it("keeps the selected version in the URL and never substitutes it", async () => {
  mount("/about/vep?version=103")
  expect(await screen.findByText("Description for 103")).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("VEP release"), { target: { value: "116" } })
  expect(await screen.findByText("Description for 116")).toBeInTheDocument()
  expect(screen.queryByText("Description for 103")).not.toBeInTheDocument()
})

it("shows an error for unavailable metadata", async () => {
  mocks.get.mockRejectedValue(new Error("Unavailable"))
  mount()
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load")
})

it("uses documentation pages and the appropriate ontology links across tabs", async () => {
  const root = "https://jun2026.archive.ensembl.org/info/"
  const data = {
    ...reference("116"),
    source: `${root}docs/tools/vep/script/vep_cache.html`,
    vc_translation_source: `${root}genome/variation/prediction/classification.html`,
    conseq_translation_source: `${root}genome/variation/prediction/predicted_data.html`,
    variant_class_translations: { SNV: { short: "SNV", displayname: "SNV", desc: "Single nucleotide variant", so_term: "SO:0001483" } },
    db_info: { GRCh37: { published_sources: { "Ensembl database version": "116" } } },
  }
  mocks.get.mockImplementation((url: string) => Promise.resolve({ data: url === "/public/vep" ? { versions: ["116"] } : data }))
  mount()
  expect(await screen.findByRole("link", { name: "Consequence definitions source" })).toHaveAttribute("href", data.conseq_translation_source)
  fireEvent.click(screen.getByRole("tab", { name: "Variant classes" }))
  expect(screen.getByRole("link", { name: "Variant classification source" })).toHaveAttribute("href", data.vc_translation_source)
  expect(screen.getByRole("link", { name: "SO:0001483" })).toHaveAttribute("href", "http://www.sequenceontology.org/miso/current_release/term/SO:0001483")
  fireEvent.click(screen.getByRole("tab", { name: "Cache sources" }))
  expect(screen.getByRole("link", { name: "Cache documentation source" })).toHaveAttribute("href", data.source)
  expect(screen.getByRole("cell", { name: "116" })).toBeInTheDocument()
  expect(screen.queryByText(/SPECIESDEFS/)).not.toBeInTheDocument()
})
