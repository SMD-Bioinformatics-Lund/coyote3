import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { AssaySetupPage } from "./AssaySetupPage"

const access = vi.hoisted(() => ({ username: "reviewer", permissions: [] as string[], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const setup = { _id: "setup-1", asp_id: "assay_1", status: "submitted", revision: 3, content_editors: ["author"], created_by: "author", content: { panel: { asp_id: "assay_1", display_name: "Synthetic assay" }, scopes: ["base"], environments: ["development"], gene_lists: [], configurations: [] } }
const context = { setup, panel_form: { fields: { asp_id: { data_type: "str", label: "Assay identifier" }, display_name: { data_type: "str", label: "Display name" } } }, subpanels: [], environments: ["development"], readiness: { ready: true, issues: [] }, history: [], rules: [] }
beforeEach(() => {
  vi.resetAllMocks()
  access.username = "reviewer"
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:create", "assay.panel:edit", "assay.config:create", "gene_list.insilico:create"]
  setup.status = "submitted"
  vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: url.endsWith("/context") ? context : { items: [setup] } }))
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: setup })
  vi.mocked(api.put).mockResolvedValue({ status: 200, data: setup })
})
function mount() {
  render(<MemoryRouter initialEntries={["/admin/assay-setups?setup=setup-1"]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AssaySetupPage /></QueryClientProvider></MemoryRouter>)
}
it("allows an independent reviewer to approve the loaded revision", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  fireEvent.click(screen.getByRole("button", { name: "Approve and activate" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/publish", { revision: 3, reason: "" }))
})
it("does not offer self-approval to a content editor", async () => {
  access.username = "author"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.queryByRole("button", { name: "Approve and activate" })).not.toBeInTheDocument()
  expect(screen.getByText("Awaiting independent review.")).toBeVisible()
})
it("allows an independent edit-only reviewer to return without publication permissions", async () => {
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:edit"]
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.queryByRole("button", { name: "Approve and activate" })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Correct the scope" } })
  fireEvent.click(screen.getByRole("button", { name: "Return for changes" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/admin/assay-setups/setup-1/return", { revision: 3, reason: "Correct the scope" }))
})
it("clears review notes when reopening a setup", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Unsubmitted notes" } })
  fireEvent.change(screen.getByLabelText("Saved setups"), { target: { value: "" } })
  fireEvent.change(screen.getByLabelText("Saved setups"), { target: { value: "setup-1" } })
  fireEvent.click(await screen.findByRole("button", { name: "6. Review" }))
  expect(screen.getByLabelText("Review notes")).toHaveValue("")
})
it("keeps the workspace read-only with view permissions", async () => {
  access.permissions = ["assay.panel:view", "assay.panel:list"]
  setup.status = "draft"
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "2. Scopes" }))
  expect(screen.getByRole("checkbox", { name: "development" })).toBeDisabled()
  expect(screen.queryByRole("button", { name: "Save scopes" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "New assay setup" })).not.toBeInTheDocument()
})
it("preserves the reserved assay identifier when saving the assay form", async () => {
  setup.status = "draft"
  mount()
  fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Updated display name" } })
  fireEvent.click(screen.getByRole("button", { name: "Save" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/admin/assay-setups/setup-1", expect.objectContaining({ revision: 3, content: expect.objectContaining({ panel: expect.objectContaining({ asp_id: "assay_1", display_name: "Updated display name" }) }) })))
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
