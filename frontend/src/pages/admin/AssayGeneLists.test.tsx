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
function mount(onChange?: (ids: string[]) => void) {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AssayGeneLists aspId="new_assay" aspGroup="hematology" readonly={false} selected={[]} onChange={onChange} />
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
