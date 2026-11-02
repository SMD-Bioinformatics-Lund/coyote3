import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { ServiceTokensPage } from "./ServiceTokensPage"

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: mocks }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: vi.fn(), notifyActionError: vi.fn() }))
const metadata = { token_id: "synthetic-id", kind: "service", audience: "testing", created_by: "issuer", created_at: "2026-11-02T12:00:00Z", name: "Synthetic pipeline", owner: "owner", operations: ["sample_upload"], asp_ids: ["assay_a"], environments: ["testing"], expires_at: "2099-01-01T00:00:00Z", revoked_at: null, last_used_at: null }
const secret = "coy3_service_SYNTHETIC_TEST_CREDENTIAL"

function renderPage(personal = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><ServiceTokensPage personal={personal} /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockImplementation((path: string) => Promise.resolve({ data: path.endsWith("/options") ? { owners: [{ username: "owner", name: "Owner" }], assays: [{ asp_id: "assay_a", name: "Assay A" }], environments: ["testing", "production"], operations: ["sample_bundle", "sample_upload", "sample_bundle_async", "sample_upload_async", "job_status"] } : { items: [metadata] } }))
  mocks.post.mockResolvedValue({ data: { token: secret, metadata } })
  mocks.delete.mockResolvedValue({ data: { ...metadata, revoked_at: "2026-11-02T12:00:00Z" } })
})

it("requires explicit scopes, creates once and dismisses the secret without storing it", async () => {
  const user = userEvent.setup()
  renderPage()
  const create = screen.getByRole("button", { name: "Create token" })
  expect(create).toBeDisabled()
  await user.type(screen.getByLabelText("Name"), "Synthetic pipeline")
  await user.selectOptions(await screen.findByLabelText("Owner"), "owner")
  await user.click(await screen.findByLabelText("Assay A (assay_a)"))
  await user.click(screen.getByLabelText("testing"))
  await user.click(create)
  expect(mocks.post).toHaveBeenCalledWith("/admin/service-tokens", { name: "Synthetic pipeline", owner: "owner", expires_hours: 720, operations: ["sample_upload"], asp_ids: ["assay_a"], environments: ["testing"] })
  expect(await screen.findByLabelText("New service token")).toHaveValue(secret)
  expect(create).toBeDisabled()
  expect(JSON.stringify(localStorage)).not.toContain(secret)
  expect(JSON.stringify(sessionStorage)).not.toContain(secret)
  await user.click(screen.getByRole("button", { name: "Dismiss secret" }))
  expect(screen.queryByLabelText("New service token")).not.toBeInTheDocument()
})

it("confirms revocation and keeps metadata lists secret-free", async () => {
  const user = userEvent.setup()
  renderPage()
  await user.click(await screen.findByRole("button", { name: "Revoke Synthetic pipeline" }))
  expect(mocks.delete).not.toHaveBeenCalled()
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Revoke token" }))
  await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith("/admin/service-tokens/synthetic-id"))
  expect(screen.queryByDisplayValue(secret)).not.toBeInTheDocument()
})

it("shows recoverable loading errors instead of an empty token list", async () => {
  mocks.get.mockRejectedValue(new Error("Unavailable"))
  renderPage()
  expect(await screen.findAllByRole("alert")).toHaveLength(2)
  expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled()
})

it("creates personal tokens without an owner field and exposes background/status capabilities", async () => {
  const user = userEvent.setup()
  renderPage(true)
  expect(screen.queryByLabelText("Owner")).not.toBeInTheDocument()
  await user.type(screen.getByLabelText("Name"), "My pipeline")
  await user.click(await screen.findByLabelText("Upload a background sample bundle"))
  await user.click(screen.getByLabelText("Read status and results of jobs submitted with this token"))
  await user.click(screen.getByLabelText("Assay A (assay_a)"))
  await user.click(screen.getByLabelText("testing"))
  await user.click(screen.getByRole("button", { name: "Create token" }))
  expect(mocks.post).toHaveBeenCalledWith("/auth/personal-tokens", {
    name: "My pipeline", expires_hours: 720, operations: ["sample_upload_async", "job_status"], asp_ids: ["assay_a"], environments: ["testing"],
  })
})

it("explains when a personal account has no supported permissions", async () => {
  mocks.get.mockImplementation((path: string) => Promise.resolve({ data: path.endsWith("/options") ? { owners: [], assays: [], environments: [], operations: [] } : { items: [] } }))
  renderPage(true)
  expect(await screen.findByText(/Your account currently has no supported ingestion permissions/)).toBeVisible()
  expect(screen.getByRole("button", { name: "Create token" })).toBeDisabled()
})
