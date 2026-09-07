import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Catalog, Version, Workspace } from "./catalog-types"

const mocks = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(),
  permissions: ["catalog:view", "catalog:draft", "catalog:submit"],
  downloadJson: vi.fn(),
}))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post, patch: mocks.patch } }))
vi.mock("@/lib/access-control", async (original) => ({
  ...await original<typeof import("@/lib/access-control")>(),
  useCurrentUserAccess: () => ({
    data: { username: "author", permissions: mocks.permissions, roles: ["catalog_author"] },
    isLoading: false,
  }),
}))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
vi.mock("@/lib/json-download", () => ({ downloadJson: mocks.downloadJson }))
import { PublicAssayCatalogPage } from "./PublicAssayCatalogPage"
import { Turnaround } from "./CatalogFields"

const catalog: Catalog = {
  header: "Public assays", description: "", version: 1, layout: { order: ["wgs"] },
  modalities: { wgs: { label: "Whole Genome Sequencing (WGS)", categories: {
    solid: { label: "Solid", asp_id: "assay", aspc_id: "assay_base", gene_lists: [], tat: "7-10 days" },
  } } },
}
let version: Version
let workspace: Workspace

function renderPage(path = "/admin/assay-catalog") {
  return render(<QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })}><MemoryRouter initialEntries={[path]}><PublicAssayCatalogPage /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.permissions = ["catalog:view", "catalog:draft", "catalog:submit"]
  version = { _id: "draft-one", status: "draft", content_version: null, revision: 1,
    base_version: 1, catalog: structuredClone(catalog), created_by: "author",
    updated_by: "author", content_editors: ["author"], review: {}, lifecycle: [] }
  workspace = { catalog: structuredClone(catalog), has_published: true, items: [version],
    sources: { asps: [{ asp_id: "assay", label: "Assay" }],
      aspcs: [{ aspc_id: "assay_base", asp_id: "assay", subpanel_id: "base" }], gene_lists: [] },
    presets: { input_material: ["DNA", "RNA"], analysis: ["somatic", "germline"],
      sample_modes: ["Tumor-only"] },
    reviewers: [{ username: "reviewer", name: "Reviewer" }], publishers: [] }
  mocks.get.mockImplementation((path: string) => Promise.resolve({
    data: path.endsWith("/versions/draft-one") ? version : workspace,
  }))
  mocks.post.mockImplementation((path: string, body?: { document?: Catalog }) =>
    Promise.resolve({ data: path.endsWith("/preview") ? body?.document : version }))
  mocks.patch.mockImplementation((_path: string, body: { catalog: Catalog }) => {
    version = { ...version, catalog: structuredClone(body.catalog), revision: version.revision + 1 }
    return Promise.resolve({ data: version })
  })
})

describe("Public assay catalog governance", () => {
  it("opens the published catalog read-only and creates a separate draft for editing", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.queryByLabelText("Catalog heading")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Edit published catalog" }))
    expect(await screen.findByLabelText("Catalog heading")).toHaveValue("Public assays")
    expect(mocks.post).toHaveBeenCalledWith("/admin/assay-catalog/drafts")
  })

  it("provides material presets, custom values, and production configuration labels", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.click(await screen.findByRole("button", { name: "Whole Genome Sequencing (WGS)" }))
    await user.click(screen.getByRole("button", { name: "Solid" }))
    await user.click(screen.getByRole("checkbox", { name: "DNA" }))
    await user.type(screen.getByLabelText("New input material"), "Custom material")
    await user.click(screen.getByRole("button", { name: "Add input material" }))
    expect(screen.getByRole("checkbox", { name: "Custom material" })).toBeChecked()
    expect(within(screen.getByLabelText("Assay configuration")).getByRole("option", { name: "base" })).toBeVisible()
    expect(screen.queryByLabelText("Catalog identifier")).not.toBeInTheDocument()
  })

  it("saves into preview before submitting the saved revision", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.type(await screen.findByLabelText("Catalog heading"), " revised")
    await user.selectOptions(screen.getByLabelText("Catalog reviewer"), "reviewer")
    expect(screen.getByRole("button", { name: "Send for approval" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.queryByLabelText("Catalog heading")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Send for approval" }))
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith(
      "/admin/assay-catalog/drafts/draft-one/submit",
      expect.objectContaining({ revision: 2, assignee: "reviewer" }),
    ))
  })

  it("does not clear the editor when the selected draft is clicked repeatedly", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.type(await screen.findByLabelText("Catalog heading"), " changed")
    const row = screen.getByRole("button", { name: /Draft by author/ })
    await user.click(row)
    await user.click(row)
    expect(screen.getByLabelText("Catalog heading")).toHaveValue("Public assays changed")
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("gives catalog viewers no editing capabilities", async () => {
    mocks.permissions = ["catalog:view"]
    renderPage()
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.getByRole("button", { name: "Edit published catalog" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Import draft" })).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument()
  })

  it("reports invalid turnaround ranges live", async () => {
    const user = userEvent.setup()
    render(<Turnaround value="7-10 days" onChange={vi.fn()} />)
    const input = screen.getByLabelText("Turnaround value or range")
    await user.clear(input)
    await user.type(input, "10-7")
    expect(input).toHaveAttribute("aria-invalid", "true")
    expect(screen.getByRole("alert")).toHaveTextContent("ascending range")
    await user.clear(input)
    await user.type(input, "7")
    expect(input).toHaveAttribute("aria-invalid", "false")
  })

  it("exports the historical revision being previewed and prevents editing it", async () => {
    const user = userEvent.setup()
    const historical = { ...version, catalog: { ...catalog, header: "Historical catalog" } }
    mocks.get.mockImplementation((path: string) => Promise.resolve({ data:
      path.endsWith("/revisions") ? { items: [{ revision: 1, document: historical }] }
        : path.endsWith("/versions/draft-one") ? version : workspace,
    }))
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByText("Revision snapshots"))
    await user.click(await screen.findByRole("button", { name: "Preview r1" }))
    expect(screen.queryByRole("button", { name: "Edit draft" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Export catalog" }))
    expect(mocks.downloadJson).toHaveBeenLastCalledWith("assay_catalog.json", historical.catalog)
    await user.click(screen.getByRole("button", { name: "Return to current revision" }))
    expect(screen.getByRole("button", { name: "Edit draft" })).toBeEnabled()
  })
})
