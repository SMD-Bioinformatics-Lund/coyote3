import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { editLease, editSessionOptions } from "@/test/edit-lease"
import { DiagnosisDefinitionsPage } from "./DiagnosisDefinitionsPage"

const access = vi.hoisted(() => ({ permissions: ["assay.panel:list", "assay.panel:view", "assay.panel:edit"], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const row = { diagnosis_id: "myeloid", display_name: "Myeloid", description: "", is_active: true, version: 2, created_by: "original.creator", updated_by: "definition.editor", associated_asp_ids: ["panel-a"] }
beforeEach(() => {
  vi.resetAllMocks()
  access.permissions = ["assay.panel:list", "assay.panel:view", "assay.panel:edit"]
  vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: url === "/resources/diagnoses" ? { diagnoses: [row] } : {
    panels: [{ asp_id: "panel-a", name: "Panel A", display_name: "Full panel A name", is_active: true }, { asp_id: "panel-b", name: "Panel B", display_name: "Full panel B name", is_active: true }], pagination: { total: 2 },
  } }))
  vi.mocked(api.post).mockImplementation(async (url) => ({ status: 201, data: url.startsWith("/editing/") ? editLease() : {} }))
  vi.mocked(api.put).mockResolvedValue({ status: 200, data: {} })
})
function mount() {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><DiagnosisDefinitionsPage /></QueryClientProvider></MemoryRouter>)
}
it("shows the recorded revision actor without claiming installer identity", async () => {
  mount()
  expect(await screen.findByRole("cell", { name: "definition.editor" })).toBeVisible()
  expect(screen.getByRole("columnheader", { name: /Updated by/ })).toBeVisible()
  expect(screen.queryByText("Unknown")).not.toBeInTheDocument()
  expect(screen.queryByRole("columnheader", { name: "Installed by" })).not.toBeInTheDocument()
})
it("creates one definition with multiple selected assays", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Create diagnosis" }))
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New scope" } })
  expect(screen.getByLabelText("Diagnosis identifier")).toHaveValue("new-scope")
  fireEvent.click(await screen.findByRole("checkbox", { name: /Panel A/ }))
  fireEvent.click(screen.getByRole("checkbox", { name: /Panel B/ }))
  fireEvent.click(screen.getByRole("button", { name: "Save diagnosis" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/diagnoses", expect.objectContaining({ diagnosis_id: "new-scope", asp_ids: ["panel-a", "panel-b"] })))
})
it("lists a shared definition only once and edits global metadata separately", async () => {
  mount()
  expect(await screen.findAllByText("Myeloid")).toHaveLength(1)
  fireEvent.click(screen.getByRole("button", { name: "Edit Myeloid" }))
  expect(screen.getByLabelText("Diagnosis identifier")).toHaveAttribute("readonly")
  expect(screen.getByRole("group", { name: "Associate assays" })).toBeInTheDocument()
  expect(await screen.findByRole("checkbox", { name: /Panel A/ })).toBeDisabled()
  expect(screen.getByRole("checkbox", { name: /Panel A/ })).toBeChecked()
  fireEvent.click(screen.getByRole("checkbox", { name: /Panel B/ }))
  fireEvent.click(screen.getByRole("button", { name: "Save diagnosis" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/resources/diagnoses/myeloid", expect.objectContaining({ expected_version: 2, add_asp_ids: ["panel-b"] }), editSessionOptions))
})
it("hides editing controls for viewers", async () => {
  access.permissions = ["assay.panel:list", "assay.panel:view"]
  mount()
  expect(await screen.findByText("Myeloid")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /Create|Edit/ })).not.toBeInTheDocument()
  const assay = await screen.findByRole("link", { name: "Panel A" })
  expect(assay).toHaveAttribute("href", "/admin/assay-diagnoses?assay=panel-a")
  expect(assay.querySelector('[data-slot="table-badge"]')).toHaveAttribute("title", "Full panel A name · panel-a")
  fireEvent.click(screen.getByRole("button", { name: "View Myeloid" }))
  const details = screen.getByRole("region", { name: "Diagnosis details" })
  expect(details).toHaveFocus()
  expect(details).toHaveTextContent("Read-only access")
  expect(api.post).not.toHaveBeenCalled()
})

it("provides a view action and explains protected system records", async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, system_installed: true }], panels: [], pagination: { total: 0 } } })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "View Myeloid" }))
  expect(screen.getByRole("region", { name: "Diagnosis details" })).toHaveTextContent("System-installed definition")
  expect(screen.queryByRole("button", { name: "Edit Myeloid" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Deactivate Myeloid" })).not.toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Close diagnosis details" }))
  expect(screen.queryByRole("region", { name: "Diagnosis details" })).not.toBeInTheDocument()
})

it("confirms global deactivation and preserves metadata with a leased revision check", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Deactivate Myeloid" }))
  const dialog = screen.getByRole("alertdialog")
  expect(dialog).toHaveTextContent("across all associated assays")
  expect(api.put).not.toHaveBeenCalled()
  fireEvent.click(within(dialog).getByRole("button", { name: "Deactivate diagnosis" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/resources/diagnoses/myeloid", {
    display_name: "Myeloid", description: "", is_active: false, expected_version: 2, add_asp_ids: [],
  }, editSessionOptions))
  await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument())
  expect(api.post).toHaveBeenCalledWith("/editing/diagnoses/myeloid/release", expect.any(Object))
})

it("allows cancellation and keeps failed activation open for reconciliation", async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, is_active: false }], panels: [], pagination: { total: 0 } } })
  vi.mocked(api.put).mockRejectedValue(new Error("Revision changed; reload before retrying"))
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Activate Myeloid" }))
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
  expect(api.put).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button", { name: "Activate Myeloid" }))
  fireEvent.click(screen.getByRole("button", { name: "Activate diagnosis" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Revision changed")
  expect(screen.getByRole("alertdialog")).toBeVisible()
  expect(api.put).toHaveBeenCalledWith("/resources/diagnoses/myeloid", expect.objectContaining({ is_active: true, expected_version: 2 }), editSessionOptions)
})
