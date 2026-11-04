import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryRouter, Link, RouterProvider } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import userEvent from "@testing-library/user-event"
import { api } from "@/lib/api"
import { installEditLeaseMock, editSessionOptions } from "@/test/edit-lease"
import { AssaySetupPage } from "./AssaySetupPage"

const access = vi.hoisted(() => ({ username: "reviewer", permissions: [] as string[], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const setup = { _id: "setup-1", asp_id: "assay_1", status: "submitted", reviewer: "reviewer", revision: 3, content_editors: ["author"], created_by: "author", content: { panel: { asp_id: "assay_1", display_name: "Synthetic assay" }, scopes: ["base"], environments: ["development"], existing_gene_list_ids: [] as string[], gene_lists: [], configurations: [] } }
const context = { setup, reviewers: [{ username: "colleague", name: "Eligible colleague" }], panel_form: { fields: { asp_id: { data_type: "str", label: "Assay identifier" }, display_name: { data_type: "str", label: "Display name" } } }, diagnoses: [], environments: ["production", "development"], readiness: { ready: true, issues: [] }, history: [], rules: [] }
beforeEach(() => {
  vi.resetAllMocks()
  access.username = "reviewer"
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:create", "assay.panel:edit", "assay.config:create", "gene_list.insilico:create"]
  setup.status = "submitted"
  setup.reviewer = "reviewer"
  setup.revision = 3
  setup.content.existing_gene_list_ids = []
  context.readiness.ready = true
  vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: url.endsWith("/context") ? context : { items: [setup] } }))
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: setup })
  vi.mocked(api.put).mockResolvedValue({ status: 200, data: setup })
})
function mount(withNavigationLink = false, history?: { entries: string[]; index: number }) {
  installEditLeaseMock(vi.mocked(api.post))
  const router = createMemoryRouter([{ path: "*", element: <><AssaySetupPage />{withNavigationLink && <Link to="/admin/aspc">Leave for configurations</Link>}</> }], { initialEntries: history?.entries || ["/admin/assay-setups?setup=setup-1"], initialIndex: history?.index })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>)
  return router
}
it("reviews imported setup content before creating an unpublished draft", async () => {
  mount()
  await screen.findByRole("button", { name: "6. Review" })
  const document = { ...setup.content, panel: { ...setup.content.panel, asp_id: "imported_panel" } }
  const file = new File([JSON.stringify(document)], "setup.json")
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(document) })
  fireEvent.change(screen.getByLabelText("Import assay setup JSON"), { target: { files: [file] } })
  await screen.findByRole("textbox", { name: "Assay setup JSON" })
  expect(api.post).not.toHaveBeenCalledWith("/admin/assay-setups", expect.anything())
  fireEvent.click(screen.getByRole("button", { name: "Save assay setup" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups", document))
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining("/publish"), expect.anything())
})
it("allows an independent reviewer to approve the loaded revision", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  fireEvent.click(screen.getByRole("button", { name: "Approve and activate" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/publish", { revision: 3, reason: "" }, {}))
})
it("labels saved setups with the assay, status and revision", async () => {
  mount()
  const picker = await screen.findByRole("combobox", { name: "Saved setups" })
  await waitFor(() => expect(picker).toHaveTextContent("Synthetic assay · assay_1 · submitted · Revision 3"))
  fireEvent.click(picker)
  expect(await screen.findByRole("option", { name: /Synthetic assay · assay_1 · submitted · Revision 3/ })).toBeVisible()
})
it("allows a content editor to activate a submitted setup without waiting for review", async () => {
  access.username = "author"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.queryByRole("button", { name: "Approve and activate" })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Publish and activate" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/publish", { revision: 3, reason: "" }, {}))
})
it("offers direct activation and optional submission for a valid draft", async () => {
  access.username = "author"
  setup.status = "draft"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  const publish = screen.getByRole("button", { name: "Publish and activate" })
  await waitFor(() => expect(publish).toBeEnabled())
  expect(screen.getByRole("button", { name: "Submit for review" })).toBeDisabled()
  fireEvent.click(publish)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/publish", { revision: 3, reason: "" }, editSessionOptions))
  expect(api.post).not.toHaveBeenCalledWith(expect.stringContaining("/submit"), expect.anything(), expect.anything())
})
it("keeps activation disabled when readiness validation fails", async () => {
  setup.status = "draft"
  context.readiness.ready = false
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.getByRole("button", { name: "Publish and activate" })).toBeDisabled()
  expect(screen.getByRole("button", { name: "Submit for review" })).toBeDisabled()
})
it("allows an author to return a submitted setup to draft with a reason", async () => {
  access.username = "author"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  const button = screen.getByRole("button", { name: "Return to draft" })
  expect(button).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Recheck dependencies" } })
  fireEvent.click(button)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/return", { revision: 3, reason: "Recheck dependencies" }, {}))
})
it("allows an independent edit-only reviewer to return without publication permissions", async () => {
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:edit"]
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.queryByRole("button", { name: "Approve and activate" })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Correct the scope" } })
  fireEvent.click(screen.getByRole("button", { name: "Return for changes" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/return", { revision: 3, reason: "Correct the scope" }, {}))
})
it("clears review notes when reopening a setup", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Unsubmitted notes" } })
  const user = userEvent.setup()
  await user.click(screen.getByRole("combobox", { name: "Saved setups" }))
  await user.click(await screen.findByRole("option", { name: "Select a setup" }))
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Saved setups" })).toHaveTextContent("Select a setup"))
  await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument())
  await user.click(screen.getByRole("combobox", { name: "Saved setups" }))
  await user.click(await screen.findByRole("option", { name: /Synthetic assay · assay_1/ }))
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.getByLabelText("Review notes")).toHaveValue("")
})
it("keeps the workspace read-only with view permissions", async () => {
  access.permissions = ["assay.panel:view", "assay.panel:list"]
  setup.status = "draft"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "2. Diagnoses" }))
  expect(screen.getByRole("checkbox", { name: "development" })).toBeDisabled()
  expect(screen.queryByRole("button", { name: "Save diagnoses and environments" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "New assay setup" })).not.toBeInTheDocument()
})
it("preserves the reserved assay identifier when saving the assay form", async () => {
  setup.status = "draft"
  mount()
  fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Updated display name" } })
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/admin/assay-setups/setup-1", expect.objectContaining({ revision: 3, content: expect.objectContaining({ panel: expect.objectContaining({ asp_id: "assay_1", display_name: "Updated display name" }) }) }), editSessionOptions))
})
it("keeps unsaved assay edits when a step change is cancelled", async () => {
  setup.status = "draft"
  mount()
  const field = await screen.findByLabelText("Display name")
  await waitFor(() => expect(field).toBeEnabled())
  fireEvent.change(field, { target: { value: "Unsaved assay name" } })
  fireEvent.click(screen.getByRole("button", { name: "2. Diagnoses" }))
  expect(await screen.findByRole("alertdialog", { name: "Discard unsaved changes?" })).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
  expect(screen.getByLabelText("Display name")).toHaveValue("Unsaved assay name")
  expect(api.put).not.toHaveBeenCalled()
})
it("explains the extra activation permission for selected shared gene lists", async () => {
  setup.content.existing_gene_list_ids = ["shared"]
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.getByRole("button", { name: "Approve and activate" })).toBeDisabled()
  expect(screen.getByRole("alert")).toHaveTextContent("gene_list.insilico:edit")
})
it("still allows optional submission when shared-list activation needs another user", async () => {
  setup.status = "draft"
  setup.content.existing_gene_list_ids = ["shared"]
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.getByRole("button", { name: "Publish and activate" })).toBeDisabled()
  const user = userEvent.setup()
  const picker = screen.getByRole("combobox", { name: "Reviewer for optional review" })
  await waitFor(() => expect(picker).toBeEnabled())
  await user.click(picker)
  await user.click(await screen.findByRole("option", { name: "Eligible colleague (colleague)" }))
  await waitFor(() => expect(screen.getByRole("button", { name: "Submit for review" })).toBeEnabled())
})
it("submits to the selected reviewer and shows the saved assignment", async () => {
  setup.status = "draft"
  vi.mocked(api.post).mockImplementation(async () => {
    setup.status = "submitted"; setup.reviewer = "colleague"; setup.revision = 4
    return { status: 200, data: setup }
  })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  const user = userEvent.setup()
  const picker = screen.getByRole("combobox", { name: "Reviewer for optional review" })
  await waitFor(() => expect(picker).toBeEnabled())
  await user.click(picker)
  await user.click(await screen.findByRole("option", { name: "Eligible colleague (colleague)" }))
  await user.click(screen.getByRole("button", { name: "Submit for review" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/submit", { revision: 3, reason: "", assignee: "colleague" }, editSessionOptions))
  expect(await screen.findByText("Assigned reviewer:", { exact: false })).toHaveTextContent("colleague")
})
it.each([
  { direction: "Back", delta: -1, entries: ["/admin", "/admin/assay-setups?setup=setup-1"], index: 1, destination: "/admin" },
  { direction: "Forward", delta: 1, entries: ["/admin/assay-setups?setup=setup-1", "/admin/aspc"], index: 0, destination: "/admin/aspc" },
])("guards browser $direction and resumes only after discard", async ({ delta, entries, index, destination }) => {
  setup.status = "draft"
  const router = mount(false, { entries, index })
  const field = await screen.findByLabelText("Display name")
  await waitFor(() => expect(field).toBeEnabled())
  fireEvent.change(field, { target: { value: "Unsaved history edit" } })
  await act(async () => { await router.navigate(delta) })
  await screen.findByRole("alertdialog", { name: "Discard unsaved changes?" })
  fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
  expect(screen.getByLabelText("Display name")).toHaveValue("Unsaved history edit")
  expect(router.state.location.pathname).toBe("/admin/assay-setups")
  await act(async () => { await router.navigate(delta) })
  fireEvent.click(await screen.findByRole("button", { name: "Discard changes" }))
  await waitFor(() => expect(router.state.location.pathname).toBe(destination))
})
it("protects unsaved edits when following an ordinary in-app link", async () => {
  setup.status = "draft"
  mount(true)
  const field = await screen.findByLabelText("Display name")
  await waitFor(() => expect(field).toBeEnabled())
  fireEvent.change(field, { target: { value: "Unsaved name" } })
  fireEvent.click(screen.getByRole("link", { name: "Leave for configurations" }))
  expect(await screen.findByRole("alertdialog", { name: "Discard unsaved changes?" })).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
  expect(screen.getByLabelText("Display name")).toHaveValue("Unsaved name")
})
it("refreshes a cached draft after acquiring its lease and saves the fresh revision", async () => {
  setup.status = "draft"
  let reads = 0
  vi.mocked(api.get).mockImplementation(async url => ({ status: 200, data: url.endsWith("/context") ? {
    ...context, setup: { ...setup, revision: ++reads === 1 ? 3 : 4, content: { ...setup.content, panel: { ...setup.content.panel, display_name: reads === 1 ? "Stale name" : "Current name" } } },
  } : { items: [setup] } }))
  mount()
  await screen.findByLabelText("Display name")
  await waitFor(() => expect(screen.getByLabelText("Display name")).toHaveValue("Current name"))
  await waitFor(() => expect(screen.getByLabelText("Display name")).toBeEnabled())
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Updated current name" } })
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/admin/assay-setups/setup-1", expect.objectContaining({ revision: 4 }), editSessionOptions))
})
it("keeps production selected and saves other environments as optional choices", async () => {
  setup.status = "draft"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "2. Diagnoses" }))
  const production = screen.getByRole("checkbox", { name: /production/ })
  expect(production).toBeChecked()
  expect(production).toBeDisabled()
  fireEvent.click(screen.getByRole("checkbox", { name: "development" }))
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/admin/assay-setups/setup-1", expect.objectContaining({ content: expect.objectContaining({ environments: ["production"] }) }), editSessionOptions))
})
it("keeps gene lists and configurations in named workspaces with explicit empty states", async () => {
  setup.status = "draft"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "3. Gene lists" }))
  expect(screen.getByRole("region", { name: "Gene list workspace" })).toBeVisible()
  expect(screen.getByText("No staged gene lists")).toBeVisible()
  expect(screen.getByRole("button", { name: "Add gene list" })).toBeDisabled()
  fireEvent.click(screen.getByRole("button", { name: "Next" }))
  expect(screen.getByRole("region", { name: "Reporting rule workspace" })).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: "Next" }))
  expect(screen.getByRole("region", { name: "Configuration workspace" })).toBeVisible()
  expect(screen.getByRole("table", { name: "Configuration coverage by scope and environment" })).toBeVisible()
  expect(screen.getByText("No configurations saved")).toBeVisible()
  expect(screen.getByRole("button", { name: "5. Configurations" })).toHaveAttribute("aria-current", "step")
})
