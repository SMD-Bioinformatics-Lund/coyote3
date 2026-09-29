import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { AssaySubpanels } from "./AssaySubpanels"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const row = { subpanel_id: "myeloid", display_name: "Myeloid", description: "", is_active: true, definition_is_active: true, version: 2 }
function mount(canEdit = true) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AssaySubpanels aspId="panel-a" canEdit={canEdit} /></QueryClientProvider>)
}
describe("Assay associations", () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { subpanels: [row] } })
    vi.mocked(api.patch).mockResolvedValue({ status: 200, data: {} })
    vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} })
  })
  it("disables status actions for viewers and shows no definition editor", async () => {
    mount(false)
    expect(await screen.findByRole("button", { name: /Deactivate/ })).toBeDisabled()
    expect(screen.queryByRole("button", { name: /Create|Edit|Save/ })).not.toBeInTheDocument()
  })
  it("changes only the selected assay status at the expected revision", async () => {
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Deactivate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/subpanels/myeloid/status", { is_active: false, expected_version: 2 }))
    expect(api.post).not.toHaveBeenCalled()
  })
  it("does not fetch or display unassociated definitions", async () => {
    vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: { subpanels: url === "/resources/subpanels" ? [row] : [] } }))
    mount()
    expect(await screen.findByText("No subpanels are associated with this assay.")).toBeVisible()
    expect(screen.queryByText("Myeloid")).not.toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith("/resources/asp/panel-a/subpanels")
    expect(api.post).not.toHaveBeenCalled()
  })
  it("keeps inactive associations visible and allows reactivation", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { subpanels: [{ ...row, is_active: false }] } })
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Activate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/subpanels/myeloid/status", { is_active: true, expected_version: 2 }))
  })
  it("does not enable a globally retired definition", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { subpanels: [{ ...row, is_active: false, definition_is_active: false }] } })
    mount()
    expect(await screen.findByRole("button", { name: /Activate/ })).toBeDisabled()
    expect(screen.getByText("Globally retired")).toBeVisible()
  })
  it("allows deactivation of a globally retired definition", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { subpanels: [{ ...row, definition_is_active: false }] } })
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Deactivate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/subpanels/myeloid/status", { is_active: false, expected_version: 2 }))
  })
  it("retains the current status after a stale-write failure", async () => {
    vi.mocked(api.patch).mockRejectedValue(new Error("Association changed"))
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Deactivate/ }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Association changed")
    expect(screen.getByRole("button", { name: /Deactivate/ })).toBeEnabled()
    expect(screen.getByText("Active", { exact: true })).toBeVisible()
  })
})
