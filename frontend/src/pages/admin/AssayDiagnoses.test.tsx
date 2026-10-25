import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { AssayDiagnoses } from "./AssayDiagnoses"
import { MemoryRouter } from "react-router-dom"

vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const row = { diagnosis_id: "myeloid", display_name: "Myeloid", description: "", is_active: true, definition_is_active: true, version: 2, created_by: "original.creator", updated_by: "association.editor" }
function mount(canEdit = true) {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AssayDiagnoses aspId="panel-a" canEdit={canEdit} /></QueryClientProvider></MemoryRouter>)
}
describe("Assay associations", () => {
  it("shows the association revision actor even for a system-installed association", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, system_installed: true }] } })
    mount()
    expect(await screen.findByRole("cell", { name: "association.editor" })).toBeVisible()
    expect(screen.getByRole("columnheader", { name: /Updated by/ })).toBeVisible()
    expect(screen.queryByText("Unknown")).not.toBeInTheDocument()
    expect(screen.queryByRole("columnheader", { name: "Installed by" })).not.toBeInTheDocument()
  })
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [row] } })
    vi.mocked(api.patch).mockResolvedValue({ status: 200, data: {} })
    vi.mocked(api.post).mockResolvedValue({ status: 201, data: {} })
  })
  it("disables status actions for viewers and shows no definition editor", async () => {
    mount(false)
    expect(await screen.findByRole("button", { name: /Deactivate/ })).toBeDisabled()
    expect(screen.getByRole("link", { name: "Myeloid" })).toHaveAttribute("href", "/admin/diagnoses?diagnosis=myeloid")
    expect(screen.queryByRole("button", { name: /Create|Edit|Save/ })).not.toBeInTheDocument()
  })
  it("changes only the selected assay status at the expected revision", async () => {
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Deactivate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/diagnoses/myeloid/status", { is_active: false, expected_version: 2 }))
    expect(api.post).not.toHaveBeenCalled()
  })
  it("does not fetch or display unassociated definitions", async () => {
    vi.mocked(api.get).mockImplementation(async (url) => ({ status: 200, data: { diagnoses: url === "/resources/diagnoses" ? [row] : [] } }))
    mount()
    expect(await screen.findByText("No diagnoses are associated with this assay.")).toBeVisible()
    expect(screen.queryByText("Myeloid")).not.toBeInTheDocument()
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledWith("/resources/asp/panel-a/diagnoses")
    expect(api.post).not.toHaveBeenCalled()
  })
  it("keeps inactive associations visible and allows reactivation", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, is_active: false }] } })
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Activate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/diagnoses/myeloid/status", { is_active: true, expected_version: 2 }))
  })
  it("does not enable a globally retired definition", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, is_active: false, definition_is_active: false }] } })
    mount()
    expect(await screen.findByRole("button", { name: /Activate/ })).toBeDisabled()
    expect(screen.getByText("Globally retired")).toBeVisible()
  })
  it("allows deactivation of a globally retired definition", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { diagnoses: [{ ...row, definition_is_active: false }] } })
    mount()
    fireEvent.click(await screen.findByRole("button", { name: /Deactivate/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/resources/asp/panel-a/diagnoses/myeloid/status", { is_active: false, expected_version: 2 }))
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
