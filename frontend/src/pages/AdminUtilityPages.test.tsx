import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  access: {
    data: { username: "admin", roles: ["superuser"], role: "superuser", access_level: 100, permissions: [] as string[] } as any,
    isLoading: false,
  },
}))

vi.mock("@/lib/api", () => ({ api: { get: mocks.get, post: mocks.post, put: mocks.put } }))
vi.mock("@/lib/notifications", () => ({ notifySuccess: mocks.success, notifyActionError: mocks.error }))
vi.mock("@/lib/access-control", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/access-control")>()
  return { ...actual, useCurrentUserAccess: () => mocks.access }
})

import { AdminAuditPage, AdminControlsPage, AdminIngestPage } from "./AdminUtilityPages"
import AdminSchemasPage from "./admin/AdminSchemasPage"

function renderPage(page: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const controlsPayload = {
  controls: {
    celery: {
      enabled: true,
      sample_ingest_enabled: true,
      collection_writes_enabled: true,
      maintenance_enabled: true,
    },
    modules: { dna_analysis_enabled: true, reports_enabled: false, knowledgebases_enabled: true },
    curation: {
      tiering: {
        small_variant_enabled: true,
        cnv_enabled: false,
        fusion_enabled: true,
        translocation_enabled: false,
      },
    },
    retention: { audit_event_days: 730, notification_days: 180 },
    updated_by: "admin",
    updated_on: "2026-08-01T10:00:00Z",
  },
  runtime: {
    observed_at: "2026-08-02T10:00:00Z",
      celery: {
        configured_enabled: true,
        configured_families: {
          sample_ingest: true,
          collection_writes: true,
          maintenance: true,
        },
      status: "online",
      execution_state: "idle",
      workers_online: 1,
      worker_names: ["worker@node"],
      worker_details: [{ name: "worker@node", status: "online", concurrency: 4, processed_count: 12, queues: ["celery"] }],
      active_count: 0,
      reserved_count: 1,
      scheduled_count: 2,
      registered_task_count: 7,
      registered_tasks: ["api.tasks.ingest"],
      beat_schedule_count: 2,
      beat_entries: [{ name: "nightly-maintenance", task: "api.tasks.maintenance", schedule: "daily" }],
      queue_consumers: { celery: ["worker@node"] },
      tasks: [{ worker: "worker@node", state: "reserved", task_id: "TASK_0", task_name: "api.tasks.ingest", queue: "celery" }],
      inspection_timeout_seconds: 0.5,
      },
      modules: {
        reports: { enabled: true, label: "Clinical reporting" },
        ingest_workspace: { enabled: false, label: "Ingest workspace" },
      },
  },
}

describe("AdminControlsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.access.data = { username: "admin", roles: ["superuser"], role: "superuser", access_level: 100, permissions: [] }
    mocks.get.mockResolvedValue({ data: controlsPayload })
    mocks.put.mockResolvedValue({ data: controlsPayload })
    mocks.post.mockResolvedValue({ data: { task_id: "MAINT_1" } })
  })

  it("shows configured controls and observed worker, queue, task, and schedule state", async () => {
    renderPage(<AdminControlsPage />)
    expect(await screen.findByRole("heading", { name: "Celery Task Families" })).toBeVisible()
    expect(screen.getByRole("switch", { name: /Allow background task execution: enabled/i })).toBeChecked()
    expect(screen.getAllByText("worker@node")).toHaveLength(2)
    expect(screen.getByText("nightly-maintenance")).toBeVisible()
    expect(screen.getByText(/TASK_0/)).toBeVisible()
    expect(screen.getByText("celery")).toBeVisible()
  })

  it("explains, changes, and persists a control without losing other settings", async () => {
    const user = userEvent.setup()
    renderPage(<AdminControlsPage />)
    const toggle = await screen.findByRole("switch", { name: /Reports: disabled/i })
    const helpButton = screen.getByRole("button", { name: "About Reports" })
    await user.click(helpButton)
    expect(screen.getByRole("tooltip")).toBeVisible()
    await user.click(toggle)
    expect(toggle).toBeChecked()
    await user.click(screen.getByRole("button", { name: "Save controls" }))
    await waitFor(() => expect(mocks.put).toHaveBeenCalledWith("/admin/controls", {
      controls: expect.objectContaining({
        modules: expect.objectContaining({ dna_analysis_enabled: true, reports_enabled: true }),
        retention: expect.objectContaining({ audit_event_days: 730 }),
      }),
    }))
    expect(mocks.success).toHaveBeenCalledWith(expect.stringContaining("saved"), expect.any(String), "Admin controls")
  })

  it("queues maintenance only when the configured task family permits it", async () => {
    const user = userEvent.setup()
    renderPage(<AdminControlsPage />)
    const button = await screen.findByRole("button", { name: "Run maintenance" })
    await waitFor(() => expect(button).toBeEnabled())
    await user.click(button)
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/admin/controls/maintenance"))
    expect(mocks.success).toHaveBeenCalledWith("Maintenance queued", expect.stringContaining("MAINT_1"), "Admin controls")
  })

  it("queues one HGNC-backed public OncoKB refresh through operational maintenance", async () => {
    const user = userEvent.setup()
    renderPage(<AdminControlsPage />)
    const button = await screen.findByRole("button", { name: "Refresh public OncoKB" })
    await waitFor(() => expect(button).toBeEnabled())
    await user.click(button)
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/admin/controls/knowledgebases/oncokb-public/refresh"))
    expect(mocks.success).toHaveBeenCalledWith(
      "Public OncoKB refresh queued",
      expect.stringContaining("MAINT_1"),
      "Knowledgebases",
    )
  })

  it("renders controls read-only when delegated permissions are absent", async () => {
    mocks.access.data = { username: "viewer", roles: ["viewer"], role: "viewer", access_level: 10, permissions: ["admin:controls:view"] }
    renderPage(<AdminControlsPage />)
    expect(await screen.findByRole("switch", { name: /Allow background task execution/i })).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Save controls" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Run maintenance" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Refresh public OncoKB" })).not.toBeInTheDocument()
  })
})

describe("AdminAuditPage", () => {
  const recentTimestamp = (hoursAgo: number) => new Date(Date.now() - hoursAgo * 60 * 60 * 1000).toISOString()
  const events = [
    {
      _id: "A1", occurred_at: recentTimestamp(1), severity: "error", category: "ingest",
      event_type: "sample.ingest.failed", message: "Sample ingest failed", outcome: "failure",
      actor: { username: "operator", fullname: "Case Operator", roles: ["operator"] },
      resource: { type: "sample", id: "OID_1", name: "SAMPLE_A" },
      source: { method: "POST", path: "/samples", request_id: "REQ_1", client_ip: "127.0.0.1" },
      tags: ["sample", "ingest"], metadata: { reason: "missing VCF" },
    },
    {
      _id: "A2", occurred_at: recentTimestamp(2), severity: "info", category: "reporting",
      event_type: "report.saved", message: "Report created", outcome: "success",
      actor: { username: "reviewer" }, resource: { type: "report", name: "REPORT_A" }, tags: ["report"],
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    mocks.get.mockResolvedValue({ data: { events } })
  })

  it("summarizes, searches, filters, clears, and exposes event context", async () => {
    const user = userEvent.setup()
    renderPage(<AdminAuditPage />)
    expect(await screen.findByText("Sample ingest failed")).toBeVisible()
    expect(screen.getByText("Report created")).toBeVisible()
    await user.click(screen.getAllByText("View details")[0])
    expect(screen.getByText("REQ_1")).toBeVisible()

    await user.click(screen.getByRole("button", { name: /^error1$/i }))
    expect(screen.getByText("Sample ingest failed")).toBeVisible()
    expect(screen.queryByText("Report created")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Clear" }))
    await user.type(screen.getByPlaceholderText("Search event, resource, or tag"), "REPORT_A")
    await user.click(screen.getByRole("button", { name: "Apply" }))
    expect(screen.getByText("Report created")).toBeVisible()
    expect(screen.queryByText("Sample ingest failed")).not.toBeInTheDocument()
  })

  it("shows a useful API failure state", async () => {
    mocks.get.mockRejectedValue(new Error("Audit store unavailable"))
    renderPage(<AdminAuditPage />)
    expect(await screen.findByText("Audit store unavailable")).toBeVisible()
  })
})

describe("AdminIngestPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.post.mockResolvedValue({ data: { task_id: "TASK_1" } })
    mocks.get.mockResolvedValue({ data: { state: "SUCCESS", ready: true, successful: true, result: { sample: "SYNTHETIC_001" } } })
  })

  it("requires a manifest and submits all files and options as multipart data", async () => {
    const user = userEvent.setup()
    renderPage(<AdminIngestPage />)
    const queue = screen.getByRole("button", { name: "Queue ingest" })
    expect(queue).toBeDisabled()
    const inputs = document.querySelectorAll<HTMLInputElement>('input[type="file"]')
    await user.upload(inputs[0], new File(["name: SYNTHETIC_001"], "sample.yaml", { type: "application/yaml" }))
    await user.upload(inputs[1], [new File(["VCF"], "sample.vcf"), new File(["{}"], "sample.cnv.json")])
    await user.click(screen.getByLabelText("Update existing sample"))
    await user.click(screen.getByLabelText("Increment sample name"))
    await user.click(queue)

    await waitFor(() => expect(mocks.post).toHaveBeenCalled())
    const [url, body] = mocks.post.mock.calls[0]
    expect(url).toBe("/internal/ingest/sample-bundle/upload/async")
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get("yaml_file")).toBeInstanceOf(File)
    expect((body as FormData).getAll("data_files")).toHaveLength(2)
    expect((body as FormData).get("update_existing")).toBe("true")
    expect((body as FormData).get("increment")).toBe("true")
    expect(await screen.findByText("TASK_1")).toBeVisible()
    expect(await screen.findByText("SUCCESS")).toBeVisible()
    expect(screen.getByText(/SYNTHETIC_001/)).toBeVisible()
  })

  it("notifies the user when ingest submission fails", async () => {
    const user = userEvent.setup()
    mocks.post.mockRejectedValue(new Error("Queue unavailable"))
    renderPage(<AdminIngestPage />)
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
    await user.upload(input, new File(["name: SYNTHETIC_002"], "sample.yaml"))
    await user.click(screen.getByRole("button", { name: "Queue ingest" }))
    await waitFor(() => expect(mocks.error).toHaveBeenCalledWith(
      "Unable to queue ingest", expect.any(Error), "Ingest workspace", expect.objectContaining({ name: "sample.yaml" }),
    ))
  })
})

describe("AdminSchemasPage", () => {
  beforeEach(() => vi.clearAllMocks())

  it("groups contracts and reveals required and optional fields", async () => {
    const user = userEvent.setup()
    mocks.get.mockResolvedValue({ data: { schemas: [
      { collection: "samples", title: "Sample", required: ["name"], properties: ["name", "case_id"] },
      { collection: "samples_filters", title: "Sample filters", required: [], properties: ["somatic", "germline"] },
      { collection: "annotations", title: "Annotation", required: ["genomic"], properties: ["genomic", "hgvsp"] },
    ] } })
    renderPage(<AdminSchemasPage />)
    expect(await screen.findByText("3 contracts")).toBeVisible()
    expect(screen.getByRole("heading", { name: "samples" })).toBeVisible()
    expect(screen.getAllByText("name")).toHaveLength(2)
    const annotation = screen.getByText("Annotation").closest("article")!
    await user.click(within(annotation).getByText("Show field names"))
    expect(within(annotation).getByText("hgvsp")).toBeVisible()
  })

  it("renders schema service errors", async () => {
    mocks.get.mockRejectedValue(new Error("Contracts unavailable"))
    renderPage(<AdminSchemasPage />)
    expect(await screen.findByText("Contracts unavailable")).toBeVisible()
  })
})
