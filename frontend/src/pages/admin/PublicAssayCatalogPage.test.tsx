import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Catalog, Version, Workspace } from "./catalog-types"
import { editLease, editSessionOptions } from "@/test/edit-lease"

const mocks = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
  permissions: ["catalog:view", "catalog:draft", "catalog:submit"],
  downloadJson: vi.fn(),
}))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post, patch: mocks.patch, delete: mocks.delete } }))
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

async function openSolidService(user: ReturnType<typeof userEvent.setup>, parentLabel?: string) {
  const tree = within(await screen.findByRole("navigation", { name: "Catalog levels" }))
  await user.click(tree.getByRole("button", { name: "WGS" }))
  if (parentLabel) {
    const parent = tree.getByRole("button", { name: parentLabel })
    await user.click(parent)
    await user.click(within(parent.closest("li")!).getByRole("button", { name: "Solid" }))
    return
  }
  await user.click(tree.getByRole("button", { name: "Solid" }))
  await user.click(tree.getByRole("button", { name: "No diagnosis / General testing" }))
  const diagnosis = tree.getByRole("button", { name: "No diagnosis / General testing" }).closest("li")!
  await user.click(within(diagnosis).getByRole("button", { name: "Solid" }))
}

async function editName(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Edit display name" }))
  return screen.getByLabelText("Display name")
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.permissions = ["catalog:view", "catalog:draft", "catalog:submit"]
  version = { _id: "draft-one", status: "draft", content_version: null, revision: 1,
    base_version: 1, catalog: structuredClone(catalog), created_by: "author",
    updated_by: "author", content_editors: ["author"], review: {}, lifecycle: [] }
  workspace = { catalog: structuredClone(catalog), has_published: true, items: [version],
    sources: { asps: [{ asp_id: "assay", label: "Assay", category: "dna", family: "wgs", group: "solid", group_label: "Solid" }],
      aspcs: [{ aspc_id: "assay_base", asp_id: "assay", diagnosis_id: "base" }], gene_lists: [] },
    presets: { input_material: ["DNA", "RNA"], analysis: ["somatic", "germline"],
      sample_modes: ["Tumor-only"] },
    reviewers: [{ username: "reviewer", name: "Reviewer" }], publishers: [] }
  mocks.get.mockImplementation((path: string) => Promise.resolve({
    data: path.endsWith("/versions/draft-one") ? version : workspace,
  }))
  mocks.post.mockImplementation((path: string, body?: { document?: Catalog }) =>
    Promise.resolve({ data: path.startsWith("/editing/") ? editLease()
      : path.endsWith("/preview/offerings") ? {
        version: 1, header: body?.document?.header || catalog.header,
        description: body?.document?.description || "", navigation: [], offerings: [],
      } : path.endsWith("/preview") ? body?.document : version }))
  mocks.patch.mockImplementation((_path: string, body: { catalog: Catalog }) => {
    version = { ...version, catalog: structuredClone(body.catalog), revision: version.revision + 1 }
    return Promise.resolve({ data: version })
  })
})

describe("Public assay catalog governance", () => {
  it.each(["", "draft-one"])("retries only the selected catalog requests (version: %s)", async (id) => {
    const user = userEvent.setup()
    let failed = true
    mocks.get.mockImplementation((path: string) => failed
      ? Promise.reject(new Error("Catalog temporarily unavailable"))
      : Promise.resolve({ data: path.endsWith("/versions/draft-one") ? version : workspace }))
    renderPage(id ? `/admin/assay-catalog?version=${id}` : "/admin/assay-catalog")
    expect(await screen.findByRole("alert")).toHaveTextContent("The catalog could not be loaded")
    mocks.get.mockClear()
    failed = false
    await user.click(screen.getByRole("button", { name: "Retry" }))
    await screen.findByRole("button", { name: id ? "Save draft" : "Edit published catalog" })
    expect(mocks.get).toHaveBeenCalledWith("/admin/assay-catalog")
    expect(mocks.get.mock.calls.some(([path]) => path === "/admin/assay-catalog/versions/")).toBe(false)
    if (id) expect(mocks.get).toHaveBeenCalledWith(`/admin/assay-catalog/versions/${id}`, expect.anything())
  })

  it.each([false, true])("does not reload a deleted version (history open: %s)", async (historyOpen) => {
    const user = userEvent.setup()
    let deleted = false
    const readsAfterDelete: string[] = []
    mocks.get.mockImplementation((path: string) => {
      if (deleted && path.includes("/versions/draft-one")) {
        readsAfterDelete.push(path)
        return Promise.reject(new Error("Catalog version not found"))
      }
      return Promise.resolve({ data: path.endsWith("/revisions") ? { items: [] } : path.endsWith("/versions/draft-one") ? version : workspace })
    })
    mocks.delete.mockImplementation(() => {
      deleted = true
      workspace = { ...workspace, items: [] }
      return Promise.resolve({ data: version })
    })
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByText("History and version options"))
    if (historyOpen) {
      await user.click(await screen.findByText("Revision snapshots"))
      await waitFor(() => expect(mocks.get).toHaveBeenCalledWith("/admin/assay-catalog/versions/draft-one/revisions", expect.anything()))
    }
    await user.click(await screen.findByRole("button", { name: "Delete draft" }))
    const dialog = screen.getByRole("alertdialog")
    await user.click(within(dialog).getByRole("button", { name: "Delete version" }))
    await screen.findByRole("button", { name: "Edit published catalog" })
    expect(mocks.delete).toHaveBeenCalledWith("/admin/assay-catalog/versions/draft-one?revision=1", editSessionOptions)
    expect(readsAfterDelete).toEqual([])
  })
  it("lets a center remove a starter modality in its first draft", async () => {
    workspace.has_published = false
    workspace.items = []
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByRole("button", { name: "Starter catalog" })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Create first draft" }))
    await user.click(await screen.findByRole("button", { name: "WGS" }))
    await user.click(screen.getByText("Section structure and source settings"))
    await user.click(screen.getByRole("button", { name: /Remove section/ }))
    expect(screen.queryByRole("button", { name: "Whole Genome Sequencing (WGS)" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    expect(mocks.patch.mock.calls[0][1].catalog.modalities).toEqual({})
    expect(mocks.patch.mock.calls[0][1].catalog.layout.order).toEqual([])
  })
  it("adds and renames a custom section without a fixed modality list", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.click(await screen.findByRole("button", { name: "Add section" }))
    const name = await editName(user)
    await user.clear(name)
    await user.type(name, "Future assay service")
    expect(screen.getByRole("button", { name: "Future assay service" })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Edit description" }))
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveAttribute("contenteditable", "true")
    await user.click(screen.getByText("Section structure and source settings"))
    await user.click(screen.getByRole("button", { name: /Remove section/ }))
    expect(screen.queryByRole("button", { name: "Future assay service" })).not.toBeInTheDocument()
  })
  it("opens the published catalog read-only and creates a separate draft for editing", async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.queryByLabelText("Catalog heading")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Edit published catalog" }))
    expect(await editName(user)).toHaveValue("Public assays")
    expect(mocks.post).toHaveBeenCalledWith("/admin/assay-catalog/drafts")
  })

  it("provides material presets, custom values, and production configuration labels", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await openSolidService(user)
    await user.click(screen.getByRole("button", { name: "Edit input material" }))
    await user.click(screen.getByRole("checkbox", { name: "DNA" }))
    await user.type(screen.getByLabelText("New input material"), "Custom material")
    await user.click(screen.getByRole("button", { name: "Add input material" }))
    expect(screen.getByRole("checkbox", { name: "Custom material" })).toBeChecked()
    await user.click(screen.getByText("Entry structure and source settings"))
    expect(within(screen.getByLabelText("Diagnosis")).getByRole("option", { name: "No diagnosis / General testing" })).toBeVisible()
    expect(screen.queryByLabelText("Catalog identifier")).not.toBeInTheDocument()
  })

  it("saves into preview before submitting the saved revision", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.type(await editName(user), " revised")
    await user.selectOptions(screen.getByLabelText("Catalog reviewer"), "reviewer")
    expect(screen.getByRole("button", { name: "Send for approval" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.queryByLabelText("Catalog heading")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Send for approval" }))
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith(
      "/admin/assay-catalog/drafts/draft-one/submit",
      expect.objectContaining({ revision: 2, assignee: "reviewer" }),
      editSessionOptions,
    ))
  })

  it("keeps same-name diagnoses distinguishable and saves the explicitly selected configuration", async () => {
    const user = userEvent.setup()
    workspace.sources.aspcs.push({ asp_id: "assay", aspc_id: "assay_alternative", diagnosis_id: "base" })
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await openSolidService(user)
    const diagnosis = screen.getByRole("combobox", { name: "Diagnosis" })
    expect(within(diagnosis).getByRole("option", { name: "No diagnosis / General testing (assay_base)" })).toBeVisible()
    expect(within(diagnosis).getByRole("option", { name: "No diagnosis / General testing (assay_alternative)" })).toBeVisible()
    await user.selectOptions(diagnosis, "assay_alternative")
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    expect(mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.solid)
      .toEqual(expect.objectContaining({ asp_id: "assay", aspc_id: "assay_alternative", diagnosis_id: "base" }))
  })

  it("does not clear the editor when the selected draft is clicked repeatedly", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await user.type(await editName(user), " changed")
    const row = screen.getByRole("button", { name: /Draft by author/ })
    await user.click(row)
    await user.click(row)
    expect(screen.getByLabelText("Display name")).toHaveValue("Public assays changed")
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("gives catalog viewers no editing capabilities", async () => {
    mocks.permissions = ["catalog:view"]
    renderPage()
    await screen.findByRole("region", { name: "Catalog preview" })
    expect(screen.getByRole("button", { name: "Edit published catalog" })).toBeDisabled()
    fireEvent.click(screen.getByText("Import and export"))
    expect(screen.getByRole("button", { name: "Import draft" })).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Save draft" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Delete draft" })).not.toBeInTheDocument()
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

  it("opens a newly added child for editing and preserves its place in the tree", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await openSolidService(user)
    await user.click(screen.getByText("Entry structure and source settings"))
    await user.click(screen.getByRole("button", { name: "Add child entry" }))
    const name = await editName(user)
    expect(name).toHaveValue("New child")
    await user.clear(name)
    await user.type(name, "MPN")
    expect(within(screen.getByRole("navigation", { name: "Catalog levels" }))
      .getByRole("button", { name: "MPN" })).toHaveAttribute("aria-current", "page")
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    const entries = mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories
    expect(Object.values(entries)).toContainEqual(expect.objectContaining({ label: "MPN", parent_key: "solid" }))
  })

  it("preserves explicitly bound lists while editing wording with inherited analyses", async () => {
    const user = userEvent.setup()
    version.catalog.modalities.wgs.analysis = ["SNV"]
    version.catalog.modalities.wgs.categories.solid.gene_lists = [
      { isgl_id: "synthetic-genes", label: "Genes", analysis: ["SNV"] },
    ]
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByRole("button", { name: "Edit draft" }))
    await openSolidService(user)
    await user.click(screen.getByRole("button", { name: "Edit subheading" }))
    await user.type(within(screen.getByRole("group", { name: "Editing subheading" }))
      .getByRole("textbox", { name: "Subheading" }), "Updated wording")
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    expect(mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.solid.gene_lists)
      .toEqual([{ isgl_id: "synthetic-genes", label: "Genes", analysis: ["SNV"] }])
  })

  it("explains a pending review and prevents an author from approving it", async () => {
    mocks.permissions.push("catalog:review")
    version.status = "submitted"
    version.review = { reviewer: "author" }
    renderPage("/admin/assay-catalog?version=draft-one")
    expect(await screen.findByText(/Waiting for review by author/)).toBeVisible()
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Publish catalog" })).not.toBeInTheDocument()
  })

  it("cancels one in-place field while preserving another field's draft edits", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await openSolidService(user)
    await user.click(screen.getByRole("button", { name: "Edit subheading" }))
    await user.type(within(screen.getByRole("group", { name: "Editing subheading" })).getByRole("textbox"), "Retained draft text")
    await user.click(within(screen.getByRole("group", { name: "Editing subheading" })).getByRole("button", { name: "Done" }))
    await user.click(screen.getByRole("button", { name: "Edit turnaround" }))
    const amount = screen.getByLabelText("Turnaround value or range")
    await user.clear(amount)
    await user.type(amount, "15")
    await user.keyboard("{Escape}")
    expect(screen.getByText("7-10 days")).toBeVisible()
    expect(screen.getByText("Retained draft text")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    const saved = mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.solid
    expect(saved.tat).toBe("7-10 days")
    expect(saved.subheading).toBe("Retained draft text")
    expect(saved.aspc_id).toBe("assay_base")
  })

  it("uses a brief DNA overview while retaining editable inherited defaults", async () => {
    const user = userEvent.setup()
    version.catalog.modalities.wgs = { ...version.catalog.modalities.wgs,
      label: "DNA", omics: "dna", description: "DNA service introduction", tat: "12 days" }
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByRole("button", { name: "Edit draft" }))
    const tree = within(await screen.findByRole("navigation", { name: "Catalog levels" }))
    await user.click(tree.getByRole("button", { name: "DNA" }))
    const overview = screen.getByRole("region", { name: "Catalog overview" })
    expect(within(overview).getByText("DNA service introduction")).toBeVisible()
    expect(within(overview).queryByText("Turnaround (TAT)")).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Edit description" })).toBeVisible()
    await user.click(screen.getByText("Inherited service defaults"))
    await user.click(screen.getByRole("button", { name: "Edit turnaround" }))
    const turnaround = screen.getByLabelText("Turnaround value or range")
    await user.clear(turnaround)
    await user.type(turnaround, "15")
    await user.click(within(screen.getByRole("group", { name: "Editing turnaround" })).getByRole("button", { name: "Done" }))
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    const saved = mocks.patch.mock.calls[0][1].catalog.modalities.wgs
    expect(saved.tat).toBe("15 days")
    expect(saved.categories.solid.tat).toBe("7-10 days")
  })

  it("creates shared defaults in the visible group and preserves registered navigation names", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    const tree = within(await screen.findByRole("navigation", { name: "Catalog levels" }))
    await user.click(tree.getByRole("button", { name: "WGS" }))
    await user.click(tree.getByRole("button", { name: "Solid" }))
    await user.click(screen.getByRole("button", { name: "Add shared defaults" }))
    const name = await editName(user)
    await user.clear(name)
    await user.type(name, "Solid service information")
    await user.click(within(screen.getByRole("group", { name: "Editing display name" })).getByRole("button", { name: "Done" }))
    expect(tree.getByRole("button", { name: "Solid" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("heading", { name: "Solid service information" })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    const entries = mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories
    expect(entries.solid.asp_id).toBe("assay")
    expect(entries.solid.aspc_id).toBe("assay_base")
    expect(entries[entries.solid.parent_key]).toEqual(expect.objectContaining({
      label: "Solid", title: "Solid service information", node_kind: "folder",
    }))
  })

  it("returns an overridden field to its immediate parent in place", async () => {
    const user = userEvent.setup()
    version.catalog.modalities.wgs.categories.parent = { label: "Parent defaults", node_kind: "folder", tat: "21 days" }
    version.catalog.modalities.wgs.categories.solid.parent_key = "parent"
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByRole("button", { name: "Edit draft" }))
    await openSolidService(user, "Parent defaults")
    await user.click(screen.getByRole("button", { name: "Edit turnaround" }))
    await user.click(screen.getByRole("button", { name: "Use parent value" }))
    expect(screen.getByText("21 days")).toBeVisible()
    expect(screen.getAllByText("Inherited from Parent defaults").length).toBeGreaterThan(0)
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    expect(mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.solid.tat).toBe("")
    expect(mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.parent.tat).toBe("21 days")
  })

  it("cancels analysis edits without losing saved gene-list bindings", async () => {
    const user = userEvent.setup()
    version.catalog.modalities.wgs.categories.solid.analysis = ["SNV", "CNV"]
    version.catalog.modalities.wgs.categories.solid.gene_lists = [{ isgl_id: "synthetic-genes", analysis: ["SNV"] }]
    workspace.presets.analysis = ["SNV", "CNV"]
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByRole("button", { name: "Edit draft" }))
    await openSolidService(user)
    await user.click(screen.getByRole("button", { name: "Edit analyses" }))
    const field = within(screen.getByRole("group", { name: "Editing analyses" }))
    await user.click(field.getByRole("checkbox", { name: "SNV" }))
    await user.click(field.getByRole("button", { name: "Cancel field edit" }))
    await user.click(screen.getByRole("button", { name: "Edit subheading" }))
    await user.type(within(screen.getByRole("group", { name: "Editing subheading" })).getByRole("textbox"), "Keep this change")
    await user.click(screen.getByRole("button", { name: "Save draft" }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalled())
    const saved = mocks.patch.mock.calls[0][1].catalog.modalities.wgs.categories.solid
    expect(saved.analysis).toEqual(["SNV", "CNV"])
    expect(saved.gene_lists).toEqual([{ isgl_id: "synthetic-genes", analysis: ["SNV"] }])
  })

  it("keeps an incomplete in-place price editable and can cancel it without saving", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    await openSolidService(user)
    await user.click(screen.getByRole("button", { name: "Edit price" }))
    await user.click(screen.getByRole("checkbox", { name: "Set a price at this level" }))
    const field = within(screen.getByRole("group", { name: "Editing price" }))
    expect(field.getByRole("button", { name: "Done" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled()
    await user.type(screen.getByLabelText("Price amount"), "450")
    await user.type(screen.getByLabelText("Currency (three-letter code)"), "SEK")
    expect(field.getByRole("button", { name: "Done" })).toBeEnabled()
    await user.click(field.getByRole("button", { name: "Cancel field edit" }))
    expect(mocks.patch).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled()
  })

  it("exposes draft deletion without opening history and retains confirmation", async () => {
    const user = userEvent.setup()
    renderPage("/admin/assay-catalog?version=draft-one")
    const remove = await screen.findByRole("button", { name: "Delete draft" })
    expect(remove).toBeVisible()
    await user.click(remove)
    expect(screen.getByRole("alertdialog")).toHaveTextContent("published catalog is preserved")
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancel" }))
    expect(mocks.delete).not.toHaveBeenCalled()
  })

  it("exposes section and child actions and shows new subsections without opening source settings", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit published catalog" }))
    expect(await screen.findByRole("button", { name: "Add section" })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Add section" }))
    expect(screen.getByRole("heading", { name: "New section" })).toBeVisible()
    expect(screen.getByText(/Add an entry or subsection to New section/)).toBeVisible()
    const actions = within(screen.getByRole("region", { name: "Add catalog content" }))
    await user.click(actions.getByRole("button", { name: "Add subsection" }))
    expect(screen.getByRole("heading", { name: "New subsection" })).toBeVisible()
    expect(within(screen.getByRole("navigation", { name: "Catalog structure" }))
      .getByRole("button", { name: "New subsection" })).toBeVisible()
    const configuration = screen.getByRole("group", { name: "Entry configuration" })
    expect(configuration).toHaveClass("surface-panel")
    expect(within(configuration).getByRole("heading", { name: "Additional entry settings" })).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Add child entry" }))
    expect(screen.getByRole("heading", { name: "New child" })).toBeVisible()
    await user.click(screen.getByText("Entry structure and source settings"))
    expect(screen.getByLabelText("Parent entry")).not.toHaveValue("")
  })

  it("guides the assigned independent publisher through the publication confirmation", async () => {
    const user = userEvent.setup()
    mocks.permissions.push("catalog:publish")
    version.status = "approved"
    version.content_editors = ["another-editor"]
    version.review = { reviewer: "reviewer", publisher: "author" }
    renderPage("/admin/assay-catalog?version=draft-one")
    expect(await screen.findByText(/Approved for publication by author/)).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Publish catalog" }))
    expect(mocks.post.mock.calls.some(([path]) => path.endsWith("/publish"))).toBe(false)
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Publish" }))
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith(
      "/admin/assay-catalog/drafts/draft-one/publish", expect.objectContaining({ revision: 1 }), expect.anything(),
    ))
  })

  it("exports the historical revision being previewed and prevents editing it", async () => {
    const user = userEvent.setup()
    const historical = { ...version, catalog: { ...catalog, header: "Historical catalog" } }
    mocks.get.mockImplementation((path: string) => Promise.resolve({ data:
      path.endsWith("/revisions") ? { items: [{ revision: 1, document: historical }] }
        : path.endsWith("/versions/draft-one") ? version : workspace,
    }))
    renderPage("/admin/assay-catalog?version=draft-one")
    await user.click(await screen.findByText("History and version options"))
    await user.click(await screen.findByText("Revision snapshots"))
    await user.click(await screen.findByRole("button", { name: "Preview r1" }))
    expect(screen.queryByRole("button", { name: "Edit draft" })).not.toBeInTheDocument()
    await user.click(screen.getByText("Import and export"))
    await user.click(screen.getByRole("button", { name: "Export catalog" }))
    expect(mocks.downloadJson).toHaveBeenLastCalledWith("assay_catalog.json", expect.objectContaining({
      header: "Historical catalog", modalities: historical.catalog.modalities,
    }))
    expect(mocks.downloadJson.mock.lastCall?.[1]).not.toHaveProperty("version")
    await user.click(screen.getByLabelText("Include metadata"))
    await user.click(screen.getByRole("button", { name: "Export catalog" }))
    expect(mocks.downloadJson.mock.lastCall?.[1]).toMatchObject({
      header: "Historical catalog", version: 1, revision: historical.revision,
    })
    await user.click(screen.getByRole("button", { name: "Return to current revision" }))
    expect(screen.getByRole("button", { name: "Edit draft" })).toBeEnabled()
  })
})
