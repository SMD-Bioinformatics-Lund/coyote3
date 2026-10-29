import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, expect, it, vi } from "vitest"
import { AdminIngestionAuditPage } from "./AdminIngestionAuditPage"

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/api", () => ({ api: { get: mocks.get } }))
const events = [
  { _id: "2", event_type: "ingest.attempt.succeeded", message: "Ingestion committed", outcome: "success", occurred_at: "2026-10-29T12:01:00Z", resource: { type: "sample", id: "synthetic", name: "SYNTHETIC" }, metadata: { attempt_id: "attempt-a", source: "upload", duration_ms: 1000 } },
  { _id: "1", event_type: "ingest.attempt.started", message: "Ingestion started", outcome: "success", occurred_at: "2026-10-29T12:00:00Z", metadata: { attempt_id: "attempt-a", source: "upload", manifest: "synthetic.yaml" } },
  { _id: "3", event_type: "ingest.attempt.unconfirmed", message: "Outcome unknown", outcome: "failure", occurred_at: "2026-10-29T12:02:00Z", metadata: { attempt_id: "attempt-b", error: "Connection interrupted" } },
]
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><AdminIngestionAuditPage /></MemoryRouter></QueryClientProvider>)
}
beforeEach(() => { vi.clearAllMocks(); mocks.get.mockResolvedValue({ data: { events, total: 1200 } }) })

it("loads only ingestion events, filters outcomes and opens correlated history", async () => {
  const user = userEvent.setup()
  mount()
  expect(await screen.findByRole("link", { name: "SYNTHETIC" })).toHaveAttribute("href", "/samples/synthetic")
  expect(mocks.get).toHaveBeenCalledWith("/admin/audit?ingestion_only=true&limit=1000")
  expect(screen.getByText(/3 latest events loaded of 1200/)).toBeVisible()
  await user.selectOptions(screen.getByLabelText("Outcome"), "Succeeded")
  expect(screen.queryByRole("button", { name: "Inspect Ingestion started" })).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Inspect Ingestion committed" }))
  const history = screen.getByRole("region", { name: "Ingestion attempt details" })
  expect(within(history).getByText("Ingestion started")).toBeVisible()
  expect(within(history).queryByText("Outcome unknown")).not.toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: "Close details" }))
  await user.click(screen.getByRole("button", { name: "Clear filters" }))
  await user.type(screen.getByLabelText("Search ingestion events"), "Connection interrupted")
  expect(screen.getByRole("button", { name: "Inspect Outcome unknown" })).toBeVisible()
  expect(screen.queryByRole("link", { name: "SYNTHETIC" })).not.toBeInTheDocument()
})

it("shows empty history without inventing attempts", async () => {
  mocks.get.mockResolvedValue({ data: { events: [], total: 0 } })
  mount()
  expect(await screen.findByText("No ingestion events have been recorded yet.")).toBeVisible()
})

it("offers recovery when the audit request fails", async () => {
  mocks.get.mockRejectedValue(new Error("Unavailable"))
  mount()
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load ingestion audit")
  expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled()
})
