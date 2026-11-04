import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { editLease, editSessionOptions } from "@/test/edit-lease"
import { AssayGeneLists } from "./AssayGeneLists"

const access = vi.hoisted(() => ({ permissions: [] as string[], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifyActionError: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.post).mockImplementation(async () => ({ status: 200, data: editLease() }))
  access.permissions = ["gene_list.insilico:list", "gene_list.insilico:edit"]
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { genelists: [{
    isgl_id: "shared", name: "Shared list", asp_ids: ["other"], asp_groups: ["other-group"], is_active: true, version: 1,
  }], pagination: { has_next: false } } })
  vi.mocked(api.put).mockResolvedValue({ status: 200, data: {} })
})
function mount(onChange?: (ids: string[]) => void, selected: string[] = []) {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AssayGeneLists aspId="new_assay" aspGroup="hematology" readonly={false} selected={selected} onChange={onChange} />
  </QueryClientProvider></MemoryRouter>)
}
it("stages links without modifying the operational gene list", async () => {
  const change = vi.fn()
  mount(change)
  fireEvent.click(await screen.findByRole("button", { name: "Link" }))
  expect(change).toHaveBeenCalledWith(["shared"])
  expect(api.put).not.toHaveBeenCalled()
})
it("links from an existing assay without losing other assay associations", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Link" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/resources/genelists/shared", {
    expected_version: 1,
    config: { asp_ids: ["other", "new_assay"], asp_groups: ["other-group", "hematology"] },
  }, editSessionOptions))
})
it("does not enable linking with list-only permission", async () => {
  access.permissions = ["gene_list.insilico:list"]
  mount()
  expect(await screen.findByRole("button", { name: "Link" })).toBeDisabled()
})
it("can remove a staged selection even when it is absent from search results", async () => {
  const change = vi.fn()
  mount(change, ["missing-list", "another-list"])
  fireEvent.click(await screen.findByRole("button", { name: "Remove selected gene list missing-list" }))
  expect(change).toHaveBeenCalledWith(["another-list"])
  expect(api.put).not.toHaveBeenCalled()
})
it("can unlink an inactive staged selection without editing its operational record", async () => {
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { genelists: [{ isgl_id: "shared", name: "Retired list", asp_ids: [], asp_groups: [], is_active: false, version: 2 }], pagination: { has_next: false } } })
  const change = vi.fn()
  mount(change, ["shared"])
  fireEvent.click(await screen.findByRole("button", { name: "Unlink" }))
  expect(change).toHaveBeenCalledWith([])
  expect(api.put).not.toHaveBeenCalled()
})
it("can clear staged selections without permission to edit operational lists", async () => {
  access.permissions = ["gene_list.insilico:list"]
  const change = vi.fn()
  mount(change, ["missing-list", "another-list"])
  fireEvent.click(await screen.findByRole("button", { name: "Clear selected lists" }))
  expect(change).toHaveBeenCalledWith([])
  expect(api.put).not.toHaveBeenCalled()
})
