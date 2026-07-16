import { ReactNode, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  Activity,
  AlertTriangle,
  BookOpenCheck,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  FileUp,
  Info,
  RefreshCw,
  Search,
  Siren,
} from "lucide-react"
import { api } from "@/lib/api"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

type Severity = "info" | "warning" | "error" | "critical"
type TimeWindow = "24h" | "7d" | "30d" | "all"

type ContractCatalogRow = {
  collection?: string
  title?: string
  required?: string[]
  properties?: string[]
}

type AuditEvent = {
  _id?: string
  occurred_at?: string
  expires_at?: string
  severity?: Severity
  category?: string
  event_type?: string
  message?: string
  outcome?: "success" | "failure" | "denied"
  actor?: {
    username?: string
    fullname?: string | null
    roles?: string[]
    provider?: string | null
  }
  resource?: {
    type?: string | null
    id?: string | null
    name?: string | null
  }
  source?: {
    environment?: string
    request_id?: string | null
    client_ip?: string | null
    method?: string | null
    path?: string | null
    user_agent?: string | null
  }
  tags?: string[]
  metadata?: Record<string, unknown>
}

function ModuleNotice({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
      {children}
    </div>
  )
}

export function AdminAuditPage() {
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState<Severity | "">("")
  const [category, setCategory] = useState("")
  const [actor, setActor] = useState("")
  const [search, setSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("7d")
  const pageSize = 50

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["admin-audit"],
    queryFn: () => api.get("/admin/audit?limit=1000").then((res) => res.data),
    retry: false,
    refetchInterval: 30_000,
  })
  const rows = useMemo(() => (data?.events || data?.audit || data?.logs || []) as AuditEvent[], [data])
  const filtered = useMemo(() => {
    const now = Date.now()
    const hours = timeWindow === "24h" ? 24 : timeWindow === "7d" ? 24 * 7 : timeWindow === "30d" ? 24 * 30 : null
    const needle = appliedSearch.toLowerCase()
    return rows.filter((event) => {
      if (severity && event.severity !== severity) return false
      if (category && event.category !== category) return false
      if (actor.trim() && !(event.actor?.username || "").toLowerCase().includes(actor.trim().toLowerCase())) return false
      if (hours && event.occurred_at) {
        const occurred = new Date(event.occurred_at).getTime()
        if (Number.isFinite(occurred) && now - occurred > hours * 60 * 60 * 1000) return false
      }
      if (!needle) return true
      const haystack = [
        event.message,
        event.event_type,
        event.category,
        event.outcome,
        event.actor?.username,
        event.actor?.fullname,
        event.resource?.type,
        event.resource?.id,
        event.resource?.name,
        event.source?.path,
        ...(event.tags || []),
      ].join(" ").toLowerCase()
      return haystack.includes(needle)
    })
  }, [actor, appliedSearch, category, rows, severity, timeWindow])
  const severityCounts = useMemo(() => {
    return rows.reduce<Record<Severity, number>>((acc, event) => {
      const level = severityValue(event.severity)
      acc[level] += 1
      return acc
    }, { info: 0, warning: 0, error: 0, critical: 0 })
  }, [rows])
  const categories = useMemo(() => Array.from(new Set(rows.map((event) => event.category).filter(Boolean) as string[])).sort(), [rows])
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const pageRows = filtered.slice((page - 1) * pageSize, page * pageSize)

  const clearFilters = () => {
    setPage(1)
    setSeverity("")
    setCategory("")
    setActor("")
    setSearch("")
    setAppliedSearch("")
    setTimeWindow("7d")
  }

  return (
    <PageShell
      eyebrow="Admin"
      title="Audit Events"
      description="Searchable security, identity, clinical activity, and system events."
      actions={
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-lg border border-primary px-3 py-2 text-sm font-semibold text-primary hover:bg-primary/10 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      }
    >
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {(["info", "warning", "error", "critical"] as Severity[]).map((level) => {
          const Icon = severityIcon[level]
          return (
            <button
              type="button"
              key={level}
              onClick={() => {
                setPage(1)
                setSeverity(severity === level ? "" : level)
              }}
              className={`flex items-center justify-between rounded-xl border p-3 text-left transition-colors duration-100 ${severityClass[level]} ${severity === level ? "ring-2 ring-current ring-offset-2 ring-offset-background" : ""}`}
            >
              <span>
                <span className="block text-xs font-bold uppercase tracking-wide">{level}</span>
                <span className="mt-0.5 block text-xl font-black tabular-nums">{severityCounts[level]}</span>
              </span>
              <Icon className="h-5 w-5" />
            </button>
          )
        })}
      </div>

      <section className="surface-panel p-3">
        <div className="grid gap-2 md:grid-cols-[minmax(13rem,1fr)_10rem_11rem_11rem_auto]">
          <form
            className="relative"
            onSubmit={(event) => {
              event.preventDefault()
              setPage(1)
              setAppliedSearch(search.trim())
            }}
          >
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search event, resource, or tag"
              className="h-9 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </form>
          <select
            value={category}
            onChange={(event) => {
              setPage(1)
              setCategory(event.target.value)
            }}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
          >
            <option value="">All categories</option>
            {categories.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select
            value={timeWindow}
            onChange={(event) => {
              setPage(1)
              setTimeWindow(event.target.value as TimeWindow)
            }}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm"
          >
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All retained</option>
          </select>
          <input
            value={actor}
            onChange={(event) => {
              setPage(1)
              setActor(event.target.value)
            }}
            placeholder="Filter by username"
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setPage(1)
                setAppliedSearch(search.trim())
              }}
              className="h-9 rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground"
            >
              Apply
            </button>
            <button type="button" onClick={clearFilters} className="h-9 rounded-lg border border-border px-3 text-sm font-semibold hover:bg-muted">
              Clear
            </button>
          </div>
        </div>
      </section>

      <section className="surface-panel overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5"><Database className="h-3.5 w-3.5" /> MongoDB audit_events</span>
          <span>{filtered.length} matching events</span>
        </div>
        {error ? (
          <div className="p-4"><ModuleNotice>{error instanceof Error ? error.message : "Unable to load audit events."}</ModuleNotice></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-muted/80 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-bold">Time</th>
                  <th className="px-3 py-2.5 font-bold">Level</th>
                  <th className="px-3 py-2.5 font-bold">Event</th>
                  <th className="px-3 py-2.5 font-bold">Actor</th>
                  <th className="px-3 py-2.5 font-bold">Resource</th>
                  <th className="px-4 py-2.5 font-bold">Context</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading ? (
                  <tr><td colSpan={6} className="p-12 text-center text-muted-foreground">Loading audit events...</td></tr>
                ) : pageRows.length ? (
                  pageRows.map((event, index) => <AuditEventRow event={event} key={event._id || `${event.occurred_at}-${index}`} />)
                ) : (
                  <tr>
                    <td colSpan={6} className="p-12 text-center text-muted-foreground">
                      <Activity className="mx-auto mb-2 h-6 w-6" />
                      No events match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
          <span className="text-muted-foreground">Page {page} of {pages}</span>
          <div className="flex gap-1">
            <button type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-md border border-border p-1.5 disabled:opacity-40">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button type="button" aria-label="Next page" disabled={page >= pages} onClick={() => setPage((value) => Math.min(pages, value + 1))} className="rounded-md border border-border p-1.5 disabled:opacity-40">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>
    </PageShell>
  )
}

const severityClass: Record<Severity, string> = {
  info: "border-primary/25 bg-primary/10 text-primary",
  warning: "border-warn/30 bg-warn/10 text-warn",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
  critical: "border-tier1/30 bg-tier1/10 text-tier1",
}

const severityIcon = {
  info: Info,
  warning: AlertTriangle,
  error: CircleAlert,
  critical: Siren,
}

function severityValue(value: unknown): Severity {
  return value === "warning" || value === "error" || value === "critical" ? value : "info"
}

function relativeTime(value: unknown) {
  if (!value) return ""
  const elapsed = Date.now() - new Date(String(value)).getTime()
  if (!Number.isFinite(elapsed)) return ""
  const minutes = Math.round(Math.abs(elapsed) / 60_000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

function AuditEventRow({ event }: { event: AuditEvent }) {
  const level = severityValue(event.severity)
  const Icon = severityIcon[level]
  const resource = event.resource?.name || event.resource?.id
  const roles = event.actor?.roles || []
  return (
    <tr className="align-top hover:bg-muted/40">
      <td className="whitespace-nowrap px-4 py-3">
        <span className="block text-sm font-semibold">{event.occurred_at ? new Date(event.occurred_at).toLocaleString() : "-"}</span>
        <span className="text-sm text-muted-foreground">{relativeTime(event.occurred_at)}</span>
      </td>
      <td className="px-3 py-3">
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-bold capitalize ${severityClass[level]}`}>
          <Icon className="h-3 w-3" /> {level}
        </span>
      </td>
      <td className="max-w-sm px-3 py-3">
        <div className="font-semibold text-foreground">{event.message || "-"}</div>
        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{event.event_type || "-"}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {(event.tags || []).slice(0, 4).map((tag) => (
            <span key={tag} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{tag}</span>
          ))}
        </div>
      </td>
      <td className="px-3 py-3">
        <span className="block font-semibold">{event.actor?.fullname || event.actor?.username || "anonymous"}</span>
        <span className="block text-sm text-muted-foreground">{event.actor?.username || "-"}</span>
        {roles.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {roles.map((role) => <span key={role} className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">{role}</span>)}
          </div>
        )}
        {event.source?.client_ip && <span className="block font-mono text-[11px] text-muted-foreground">{event.source.client_ip}</span>}
      </td>
      <td className="px-3 py-3">
        <span className="block text-sm font-bold capitalize">{event.resource?.type?.replaceAll("_", " ") || "-"}</span>
        <span className="block max-w-48 truncate font-mono text-[11px] text-muted-foreground" title={resource || ""}>{resource || "-"}</span>
      </td>
      <td className="px-4 py-3">
        <div className="mb-1 flex items-center gap-1.5">
          <span className={`size-1.5 rounded-full ${event.outcome === "success" ? "bg-pass" : "bg-destructive"}`} />
          <span className="text-sm capitalize">{event.outcome || "unknown"}</span>
          <span className="text-sm text-muted-foreground">- {event.category || "uncategorized"}</span>
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer text-primary">View event details</summary>
          <div className="mt-2 w-80 space-y-1 rounded-lg bg-muted/60 p-2 text-[11px]">
            <Detail label="Request ID" value={event.source?.request_id} />
            <Detail label="Request" value={event.source?.method && event.source?.path ? `${event.source.method} ${event.source.path}` : null} />
            <Detail label="Provider" value={event.actor?.provider} />
            <Detail label="Expires" value={event.expires_at ? new Date(event.expires_at).toLocaleDateString() : null} />
            {event.metadata && Object.keys(event.metadata).length > 0 && (
              <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-background p-2">{JSON.stringify(event.metadata, null, 2)}</pre>
            )}
          </div>
        </details>
      </td>
    </tr>
  )
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="grid grid-cols-[5rem_1fr] gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all font-mono">{value}</span>
    </div>
  )
}

export function AdminIngestPage() {
  const [yamlFile, setYamlFile] = useState<File | null>(null)
  const [dataFiles, setDataFiles] = useState<File[]>([])
  const [updateExisting, setUpdateExisting] = useState(false)
  const [increment, setIncrement] = useState(false)
  const [taskId, setTaskId] = useState("")
  const taskStatus = useQuery({
    queryKey: ["internal-task", taskId],
    enabled: Boolean(taskId),
    queryFn: () => api.get(`/internal/tasks/${taskId}`).then((res) => res.data),
    refetchInterval: (query) => query.state.data?.ready ? false : 2000,
    retry: false,
  })
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!yamlFile) throw new Error("Select a coyote3 YAML manifest before submitting.")
      const formData = new FormData()
      formData.append("yaml_file", yamlFile)
      dataFiles.forEach((file) => formData.append("data_files", file))
      formData.append("update_existing", String(updateExisting))
      formData.append("increment", String(increment))
      return api.post("/internal/ingest/sample-bundle/upload/async", formData).then((res) => res.data)
    },
    onSuccess: (payload) => {
      setTaskId(String(payload.task_id || ""))
      notifySuccess("Ingest queued", `${yamlFile?.name || "Sample bundle"} was submitted to the ingest worker.`, "Ingest workspace", {
        type: "ingest",
        id: String(payload.task_id || ""),
        name: yamlFile?.name,
      })
    },
    onError: (error) => {
      notifyActionError("Unable to queue ingest", error, "Ingest workspace", {
        type: "ingest",
        name: yamlFile?.name || "sample bundle",
      })
    },
  })

  return (
    <PageShell eyebrow="Admin" title="Ingest Workspace" description="Validate and enqueue sample-bundle ingestion through the internal API and Celery ingest workers.">
      <div className="grid gap-3 xl:grid-cols-2">
        <section className="surface-panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <FileUp className="h-5 w-5 text-dna" />
            <h2 className="text-lg font-bold">Sample Bundle Upload</h2>
          </div>
          <div className="space-y-3">
            <label className="block space-y-1">
              <span className="text-xs font-bold uppercase text-muted-foreground">YAML manifest</span>
              <input
                type="file"
                accept=".yaml,.yml"
                onChange={(event) => setYamlFile(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-bold uppercase text-muted-foreground">Referenced data files</span>
              <input
                type="file"
                multiple
                onChange={(event) => setDataFiles(Array.from(event.target.files || []))}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="flex items-center gap-2 rounded-lg border border-border bg-background/70 px-3 py-2 text-sm font-semibold">
                <input type="checkbox" checked={updateExisting} onChange={(event) => setUpdateExisting(event.target.checked)} />
                Update existing sample
              </label>
              <label className="flex items-center gap-2 rounded-lg border border-border bg-background/70 px-3 py-2 text-sm font-semibold">
                <input type="checkbox" checked={increment} onChange={(event) => setIncrement(event.target.checked)} />
                Increment sample name
              </label>
            </div>
            <button
              type="button"
              onClick={() => uploadMutation.mutate()}
              disabled={!yamlFile || uploadMutation.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50"
            >
              {uploadMutation.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
              Queue ingest
            </button>
          </div>
        </section>
        <section className="surface-panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <Database className="h-5 w-5 text-rna" />
            <h2 className="text-lg font-bold">Worker Task</h2>
          </div>
          {taskId ? (
            <div className="space-y-3">
              <div className="rounded-xl border border-border bg-background/70 p-3">
                <p className="text-xs font-bold uppercase text-muted-foreground">Task ID</p>
                <p className="break-all font-mono text-sm">{taskId}</p>
              </div>
              {taskStatus.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground"><Activity className="h-4 w-4 animate-spin" /> Checking worker state...</div>
              ) : taskStatus.error ? (
                <ModuleNotice>{taskStatus.error instanceof Error ? taskStatus.error.message : "Unable to read task state."}</ModuleNotice>
              ) : (
                <div className="space-y-2">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <TaskMetric label="State" value={taskStatus.data?.state || "-"} />
                    <TaskMetric label="Ready" value={taskStatus.data?.ready ? "yes" : "no"} />
                    <TaskMetric label="Successful" value={taskStatus.data?.successful === null || taskStatus.data?.successful === undefined ? "-" : taskStatus.data?.successful ? "yes" : "no"} />
                  </div>
                  {taskStatus.data?.error && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                      {String(taskStatus.data.error)}
                    </div>
                  )}
                  {taskStatus.data?.result && (
                    <div className="rounded-lg border border-pass/30 bg-pass/10 p-3 text-sm">
                      <p className="font-bold text-pass">Ingest result</p>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(taskStatus.data.result, null, 2)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Submit a YAML manifest to enqueue an ingest task. The worker status appears here until the task completes.
            </p>
          )}
        </section>
      </div>
    </PageShell>
  )
}

function TaskMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background/70 p-3">
      <p className="text-[11px] font-bold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-black">{value}</p>
    </div>
  )
}

export function AdminSchemasPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-schemas"],
    queryFn: () => api.get("/admin/schemas").then((res) => res.data),
    retry: false,
  })
  const rows: ContractCatalogRow[] = useMemo(() => data?.schemas || data?.items || [], [data])
  const groupedRows = useMemo(() => {
    return rows.reduce((acc: Record<string, ContractCatalogRow[]>, row) => {
      const group = String(row.collection || "other").split("_")[0] || "other"
      acc[group] = [...(acc[group] || []), row]
      return acc
    }, {})
  }, [rows])

  return (
    <PageShell
      eyebrow="Admin"
      title="Contract Catalog"
      description="Backend-owned Pydantic contracts and admin form sources used by the API, ingest, and managed-resource editors."
    >
      <section className="surface-panel p-3">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3 px-1">
          <div className="flex items-start gap-2">
            <BookOpenCheck className="mt-0.5 h-5 w-5 text-panel" />
            <div>
              <h2 className="text-lg font-bold">Managed Collection Contracts</h2>
              <p className="text-sm text-muted-foreground">
                These contracts are inspectable for support and QA. They are not edited here; managed resources are edited through their dedicated admin forms.
              </p>
            </div>
          </div>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-xs font-bold text-muted-foreground">
            {rows.length} contracts
          </span>
        </div>
        {isLoading ? <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div> : error ? (
          <ModuleNotice>{error instanceof Error ? error.message : "Unable to load schema contracts."}</ModuleNotice>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {Object.entries(groupedRows).map(([group, contracts]) => (
              <div key={group} className="rounded-xl border border-border bg-background/60 p-3">
                <h3 className="mb-2 text-sm font-black uppercase tracking-wide text-foreground">{group}</h3>
                <div className="space-y-2">
                  {contracts.map((contract) => (
                    <article key={contract.collection} className="rounded-lg border border-border bg-card p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h4 className="text-sm font-black">{contract.title || contract.collection}</h4>
                          <p className="font-mono text-xs text-muted-foreground">{contract.collection}</p>
                        </div>
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
                          {(contract.properties || []).length} fields
                        </span>
                      </div>
                      {(contract.required || []).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {(contract.required || []).map((field: string) => (
                            <span key={field} className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-[10px] font-bold text-destructive">
                              {field}
                            </span>
                          ))}
                        </div>
                      )}
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs font-bold text-primary">Show field names</summary>
                        <div className="mt-2 flex max-h-28 flex-wrap gap-1 overflow-auto rounded-lg bg-muted/40 p-2">
                          {(contract.properties || []).map((field: string) => (
                            <span key={field} className="rounded bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                              {field}
                            </span>
                          ))}
                        </div>
                      </details>
                    </article>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </PageShell>
  )
}
