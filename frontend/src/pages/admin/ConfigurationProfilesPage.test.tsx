import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { ConfigurationProfilesPage } from "./ConfigurationProfilesPage"
import { downloadJson } from "@/lib/json-download"

const access = vi.hoisted(() => ({ username: "reviewer", permissions: [] as string[], roles: [] }))
vi.mock("@/lib/access-control", async (original) => ({ ...await original<typeof import("@/lib/access-control")>(), useCurrentUserAccess: () => ({ data: access, isLoading: false }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
vi.mock("@/lib/json-download", () => ({ downloadJson: vi.fn() }))
const profile = { _id: "profile-1", name: "Solid depth", profile_id: "solid_depth", kind: "filters", version: 2, status: "draft", created_by: "author", content_hash: "a".repeat(64), content: {}, bindings: [{ asp_group: "solid" }] }
beforeEach(() => {
  vi.resetAllMocks()
  access.username = "reviewer"
  access.permissions = ["assay.config:list", "assay.config:create", "configuration:publish"]
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: [profile] })
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: profile })
})
function mount() {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ConfigurationProfilesPage /></QueryClientProvider></MemoryRouter>)
}

it("exports editable profile fields and imports them for review without publishing", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Export JSON" }))
  const portable = { profile_id: profile.profile_id, name: profile.name, kind: profile.kind,
    bindings: profile.bindings, content: profile.content, reason: "" }
  expect(downloadJson).toHaveBeenCalledWith("solid_depth-profile", portable)
  const file = new File([JSON.stringify(portable)], "profile.json")
  Object.defineProperty(file, "text", { value: async () => JSON.stringify(portable) })
  fireEvent.change(screen.getByLabelText("Import configuration profile JSON"), { target: { files: [file] } })
  const editor = await screen.findByRole("textbox", { name: "Configuration JSON" })
  expect(JSON.parse((editor as HTMLTextAreaElement).value)).toEqual(portable)
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.change(editor, { target: { value: JSON.stringify({ ...portable, reason: "Reviewed import" }) } })
  fireEvent.click(screen.getByRole("button", { name: "Save configuration" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/configuration-profiles", {
    ...portable, reason: "Reviewed import",
  }))
})
it("publishes the reviewed hash only after a review reason is supplied", async () => {
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Review" }))
  const publish = screen.getByRole("button", { name: "Publish reviewed profile" })
  expect(publish).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Review decision"), { target: { value: "Validated depth evidence" } })
  fireEvent.click(publish)
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/resources/configuration-profiles/profile-1/publish", { content_hash: profile.content_hash, reason: "Validated depth evidence" }))
})
it("prevents self approval and hides publication from readers", async () => {
  access.username = "author"
  access.permissions = ["assay.config:list"]
  mount()
  fireEvent.click(await screen.findByRole("button", { name: "Review" }))
  expect(screen.getByText("Another authorized user must approve this draft.")).toBeVisible()
  expect(screen.queryByRole("button", { name: "Publish reviewed profile" })).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Create profile" })).not.toBeInTheDocument()
})
it("loads promotion proposals separately from profiles", async () => {
  mount()
  fireEvent.click(screen.getByRole("button", { name: "Environment promotions" }))
  await waitFor(() => expect(api.get).toHaveBeenCalledWith("/resources/configuration-promotions"))
  expect(screen.getByRole("button", { name: "Propose promotion" })).toBeVisible()
})
