import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { AssayGroupsPage } from "./AssayGroupsPage"

const access = vi.hoisted(() => ({ permissions: ["assay.panel:view", "assay.panel:edit"], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  access.permissions = ["assay.panel:view", "assay.panel:edit"]
  const group = { group_id: "solid", display_name: "Solid tumors", description: "", system_managed: true, is_active: true, version: 1 }
  vi.mocked(api.get).mockImplementation(async (path) => ({ status: 200, data: path.endsWith("/impact") ? { group, assays: ["panel-a"] } : { groups: [group] } }))
  vi.mocked(api.patch).mockResolvedValue({ status: 200, data: {} })
  vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} })
})
function mount() {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AssayGroupsPage /></QueryClientProvider></MemoryRouter>)
}
it("shows protected system entries without edit or delete actions", async () => {
  mount()
  expect(await screen.findByText("Solid tumors")).toBeVisible()
  const registry = screen.getByRole("region", { name: "Assay group registry" })
  expect(registry).toHaveClass("glass-card")
  expect(registry).toContainElement(screen.getByRole("textbox", { name: "Search assay groups" }))
  expect(registry).toContainElement(screen.getByRole("table"))
  expect(screen.getByText("System")).toBeVisible()
  expect(screen.queryByRole("button", { name: /Edit|Delete/ })).not.toBeInTheDocument()
})
it("creates a custom group with an editable generated identifier", async () => {
  mount()
  fireEvent.click(screen.getByRole("button", { name: "Create group" }))
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New group" } })
  expect(screen.getByLabelText(/Group identifier/)).toHaveValue("new_group")
  fireEvent.change(screen.getByLabelText(/Group identifier/), { target: { value: "custom" } })
  fireEvent.click(screen.getByRole("button", { name: "Save group" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/assay-groups", { group_id: "custom", display_name: "New group", description: "" }))
})
it("rejects invalid identifiers before submitting", () => {
  mount()
  fireEvent.click(screen.getByRole("button", { name: "Create group" }))
  fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Test" } })
  fireEvent.change(screen.getByLabelText(/Group identifier/), { target: { value: "two words" } })
  expect(screen.getByLabelText(/Group identifier/)).toHaveAttribute("aria-invalid", "true")
  expect(screen.getByRole("button", { name: "Save group" })).toBeDisabled()
  expect(api.post).not.toHaveBeenCalled()
})
it("limits viewers to the searchable registry", async () => {
  access.permissions = ["assay.panel:view"]
  mount()
  expect(await screen.findByText("Solid tumors")).toBeVisible()
  expect(screen.queryByRole("button", { name: "Create group" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /Deactivate/ })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Search assay groups"), { target: { value: "missing" } })
  expect(screen.getByText("No assay groups found.")).toBeVisible()
})

it("shows affected assays and requires a reason before deactivating a system group", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Deactivate Solid tumors" }))
  expect(await screen.findByText("panel-a")).toBeVisible()
  const confirm = screen.getByRole("button", { name: "Deactivate group" })
  await waitFor(() => expect(confirm).toBeEnabled())
  fireEvent.click(confirm)
  expect(api.patch).not.toHaveBeenCalled()
  expect(screen.getByRole("alert")).toHaveTextContent("Enter a reason")
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Pause new work" } })
  fireEvent.click(confirm)
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/assay-groups/solid/status", {
    is_active: false, expected_version: 1, reason: "Pause new work",
  }))
})

it("blocks stale group changes when impact has a newer version", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => path.endsWith("/impact")
    ? { status: 200, data: { group: { version: 2 }, assays: [] } }
    : original(path, options))
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Deactivate Solid tumors" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("This group has changed")
  expect(screen.getByRole("button", { name: "Deactivate group" })).toBeDisabled()
  expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled()
  expect(api.patch).not.toHaveBeenCalled()
})

it("allows closing an impact failure without enabling the mutation", async () => {
  const original = vi.mocked(api.get).getMockImplementation()!
  vi.mocked(api.get).mockImplementation(async (path, options) => {
    if (path.endsWith("/impact")) throw new Error("Unavailable")
    return original(path, options)
  })
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Deactivate Solid tumors" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load affected assays")
  expect(screen.getByRole("button", { name: "Deactivate group" })).toBeDisabled()
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
})
