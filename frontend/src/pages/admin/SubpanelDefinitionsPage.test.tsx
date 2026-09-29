import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { SubpanelDefinitionsPage } from "./SubpanelDefinitionsPage"

const access = vi.hoisted(() => ({ permissions: ["assay.panel:list", "assay.panel:view", "assay.panel:edit"], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const row = { subpanel_id: "myeloid", display_name: "Myeloid", description: "", is_active: true, version: 2, associated_asp_ids: ["panel-a"] }
beforeEach(() => {
  vi.resetAllMocks()
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:edit"]
  vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: url === "/resources/subpanels" ? { subpanels: [row] } : {
    panels: [{ asp_id: "panel-a", display_name: "Panel A", is_active: true }, { asp_id: "panel-b", display_name: "Panel B", is_active: true }], pagination: { total: 2 },
  } }))
  vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} })
  vi.mocked(api.put).mockResolvedValue({ status: 200, data: {} })
})
function mount() {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><SubpanelDefinitionsPage /></QueryClientProvider></MemoryRouter>)
}
it("creates one definition with multiple selected assays", async () => {
  mount()
  fireEvent.click(screen.getByRole("button", { name: "Create subpanel" }))
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New scope" } })
  expect(screen.getByLabelText("Subpanel identifier")).toHaveValue("new-scope")
  fireEvent.click(await screen.findByRole("checkbox", { name: /Panel A/ }))
  fireEvent.click(screen.getByRole("checkbox", { name: /Panel B/ }))
  fireEvent.click(screen.getByRole("button", { name: "Save subpanel" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/subpanels", expect.objectContaining({ subpanel_id: "new-scope", asp_ids: ["panel-a", "panel-b"] })))
})
it("lists a shared definition only once and edits global metadata separately", async () => {
  mount()
  expect(await screen.findAllByText("Myeloid")).toHaveLength(1)
  fireEvent.click(screen.getByRole("button", { name: "Edit Myeloid" }))
  expect(screen.getByLabelText("Subpanel identifier")).toHaveAttribute("readonly")
  expect(screen.getByRole("group", { name: "Associate assays" })).toBeInTheDocument()
  expect(await screen.findByRole("checkbox", { name: /Panel A/ })).toBeDisabled()
  expect(screen.getByRole("checkbox", { name: /Panel A/ })).toBeChecked()
  fireEvent.click(screen.getByRole("checkbox", { name: /Panel B/ }))
  fireEvent.click(screen.getByRole("button", { name: "Save subpanel" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/resources/subpanels/myeloid", expect.objectContaining({ expected_version: 2, add_asp_ids: ["panel-b"] })))
})
it("hides editing controls for viewers", async () => {
  access.permissions = ["assay.panel:list", "assay.panel:view"]
  mount()
  expect(await screen.findByText("Myeloid")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /Create|Edit/ })).not.toBeInTheDocument()
})
