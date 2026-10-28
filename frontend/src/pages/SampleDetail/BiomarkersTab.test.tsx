import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { BiomarkersTab } from "./BiomarkersTab"

const access = vi.hoisted(() => ({ permissions: ["sample:edit:own"] }))
const editor = vi.hoisted(() => ({ owned: true, pending: false, options: () => ({ headers: { "X-Edit-Session": "synthetic-editor" } }) }))
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), patch: vi.fn() } }))
vi.mock("@/lib/access-control", () => ({
  useCurrentUserAccess: () => ({ data: access }),
  hasPermission: (user: typeof access, permission: string) => user.permissions.includes(permission),
}))
vi.mock("@/hooks/useDocumentEditor", () => ({ useDocumentEditor: () => editor }))

const record = { _id: "synthetic-row", name: "Synthetic source", TMB: { value: 0, unit: "mut/Mb" } }
const payload = { analysis_types: ["TMB"], biomarkers: [record] }

function show(production = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { ...render(<QueryClientProvider client={client}><BiomarkersTab sampleId="SYNTHETIC" production={production} /></QueryClientProvider>), client }
}

beforeEach(() => {
  vi.clearAllMocks()
  access.permissions = ["sample:edit:own"]
  editor.owned = true
  vi.mocked(api.get).mockResolvedValue({ data: payload, status: 200 })
})

describe("manual biomarker review", () => {
  it("retains the revision reviewed when editing began after a background refresh", async () => {
    const user = userEvent.setup()
    vi.mocked(api.patch).mockRejectedValue(new Error("Assessment changed"))
    const view = show()
    await user.click(await screen.findByRole("button", { name: "Edit TMB assessment" }))
    act(() => view.client.setQueryData(["sample-biomarkers", "SYNTHETIC"], {
      ...payload, biomarkers: [{ ...record, TMB: { ...record.TMB, clinical_assessment: {
        value: "LOW", revision: 1, assessed_by: "Another reviewer", assessed_at: "2026-10-28T12:00:00Z",
      } } }],
    }))
    await user.click(screen.getByRole("button", { name: "Save assessment" }))
    await screen.findByRole("alert")
    expect(api.patch).toHaveBeenCalledWith(expect.any(String),
      { value: null, expected_revision: 0 }, expect.any(Object))
  })

  it("does not infer an assessment and saves only the selected value with its revision", async () => {
    const user = userEvent.setup()
    const assessment = { value: "HIGH", revision: 1, assessed_by: "Synthetic reviewer", assessed_at: "2026-10-28T12:00:00Z" }
    vi.mocked(api.patch).mockResolvedValue({ status: 200, data: { ...payload, biomarkers: [{ ...record, TMB: { ...record.TMB, clinical_assessment: assessment } }] } })
    show()
    await screen.findByText("Not assessed")
    expect(screen.getByText("0 mut/Mb")).toBeVisible()
    await user.click(screen.getByRole("button", { name: "Edit TMB assessment" }))
    await user.click(screen.getByRole("combobox", { name: "TMB clinical assessment" }))
    await user.click(screen.getByRole("option", { name: "High" }))
    await user.click(screen.getByRole("button", { name: "Save assessment" }))
    await screen.findByText("HIGH")
    expect(api.patch).toHaveBeenCalledWith(
      "/samples/SYNTHETIC/biomarkers/synthetic-row/assessments/TMB",
      { value: "HIGH", expected_revision: 0 },
      { headers: { "X-Edit-Session": "synthetic-editor" } },
    )
    expect(screen.getByText(/Saved by Synthetic reviewer/)).toBeVisible()
    expect(screen.getByText("0 mut/Mb")).toBeVisible()
  })

  it("requires publication permission for production samples", async () => {
    show(true)
    await screen.findByText("Not assessed")
    expect(screen.queryByRole("button", { name: "Edit TMB assessment" })).not.toBeInTheDocument()
  })

  it("keeps a failed edit visible and never retries it automatically", async () => {
    const user = userEvent.setup()
    vi.mocked(api.patch).mockRejectedValue(new Error("Biomarker assessment changed. Reload before saving again."))
    show()
    await user.click(await screen.findByRole("button", { name: "Edit TMB assessment" }))
    await user.click(screen.getByRole("button", { name: "Save assessment" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Reload before saving again")
    expect(api.patch).toHaveBeenCalledTimes(1)
    expect(screen.getByRole("combobox")).toBeVisible()
  })

  it("shows empty, loading and failed reads without fabricated measurements", async () => {
    vi.mocked(api.get).mockResolvedValue({ status: 200, data: { ...payload, biomarkers: [] } })
    const view = show()
    expect(await screen.findByText(/No measured biomarkers/)).toBeVisible()
    view.unmount()
    vi.mocked(api.get).mockRejectedValue(new Error("Unable to load biomarker results"))
    show()
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Unable to load"))
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument()
  })
})
