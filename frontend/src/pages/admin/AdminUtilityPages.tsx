import { ReactNode, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import {
  Activity,
  AlertTriangle,
  CircleAlert,
  Database,
  FileUp,
  Info,
  RefreshCw,
  Save,
  Search,
  Settings2,
  Siren,
  SlidersHorizontal,
  Tags,
} from "lucide-react"
import { api } from "@/lib/api"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { TimeDisplay } from "@/components/ui/time-display"
import { DataTable } from "@/components/data-table/DataTable"
import { fullDateTime, localDate } from "@/lib/detail-formatters"
import { appControlHelp } from "@/lib/app-control-metadata"
import { APPLICATION_MODULES_QUERY_KEY } from "@/lib/app-module-state"
import {
  ADMIN_UTILITY_PERMISSIONS,
  hasPermission,
  useCurrentUserAccess,
} from "@/lib/access-control"

import {
  BeatRuntimePanel,
  ControlHelp,
  ControlSection,
  ControlToggle,
  EffectiveStatePanel,
  QueueRuntimePanel,
  RuntimeExecutionSummary,
  RuntimeMetric,
  RuntimeStatusBadge,
  TaskRuntimePanel,
  WorkerRuntimePanel,
} from "@/pages/admin/runtime-panels"

type Severity = "info" | "warning" | "error" | "critical"
type TimeWindow = "24h" | "7d" | "30d" | "all"


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

type AppControls = {
  celery: Record<string, boolean>
  retention: Record<string, number>
  modules: Record<string, boolean>
  curation: {
    tiering: Record<string, boolean>
  }
  updated_by?: string | null
  updated_on?: string | null
}

type AppControlsRuntime = {
  observed_at?: string
  celery?: {
    configured_enabled?: boolean
    configured_families?: Record<string, boolean>
    status?: string
    execution_state?: string
    workers_online?: number
    worker_names?: string[]
    worker_details?: {
      name?: string
      status?: string
      pid?: number | null
      uptime_seconds?: number | null
      pool?: string | null
      concurrency?: number | null
      processed_count?: number
      active_count?: number
      reserved_count?: number
      scheduled_count?: number
      registered_count?: number
      queues?: string[]
    }[]
    active_count?: number
    reserved_count?: number
    scheduled_count?: number
    registered_task_count?: number
    registered_tasks?: string[]
    beat_schedule_count?: number
    beat_entries?: { name?: string; task?: string; schedule?: string }[]
    queue_names?: string[]
    queue_consumers?: Record<string, string[]>
    tasks?: {
      worker?: string
      state?: string
      task_id?: string | null
      task_name?: string | null
      queue?: string | null
      eta?: string | null
      started_at?: number | string | null
    }[]
    inspection_timeout_seconds?: number
    error?: string | null
  }
  modules?: Record<string, { enabled?: boolean; label?: string }>
  index_setup_conflicts?: { repository?: string; code?: string; message?: string }[]
}

export function AdminControlsPage() {
  const queryClient = useQueryClient()
  const accessQuery = useCurrentUserAccess()
  const canEdit = hasPermission(accessQuery.data, ADMIN_UTILITY_PERMISSIONS.controlsEdit)
  const canRunMaintenance = hasPermission(accessQuery.data, ADMIN_UTILITY_PERMISSIONS.maintenanceRun)
  const [draft, setDraft] = useState<AppControls | null>(null)
  const controlsQuery = useQuery({
    queryKey: ["admin-controls"],
    queryFn: () => api.get("/admin/controls").then((res) => res.data),
    retry: false,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  })
  const controls = (draft || controlsQuery.data?.controls || null) as AppControls | null
  const runtime = (controlsQuery.data?.runtime || {}) as AppControlsRuntime

  const saveControls = useMutation({
    mutationFn: (controlsPayload: AppControls) => api.put("/admin/controls", { controls: controlsPayload }).then((res) => res.data),
    onSuccess: (data) => {
      setDraft(data.controls)
      controlsQuery.refetch()
      queryClient.invalidateQueries({ queryKey: APPLICATION_MODULES_QUERY_KEY })
      notifySuccess("Application controls saved", "Runtime controls and retention settings were updated.", "Admin controls")
    },
    onError: (error) => notifyActionError("Unable to save application controls", error, "Admin controls"),
  })

  const runMaintenance = useMutation({
    mutationFn: () => api.post("/admin/controls/maintenance").then((res) => res.data),
    onSuccess: (data) => notifySuccess("Maintenance queued", `Task ${data.task_id || "queued"} will run cleanup policies.`, "Admin controls"),
    onError: (error) => notifyActionError("Unable to queue maintenance", error, "Admin controls"),
  })

  const refreshPublicOncoKb = useMutation({
    mutationFn: () => api.post("/admin/controls/knowledgebases/oncokb-public/refresh").then((res) => res.data),
    onSuccess: (data) => notifySuccess("Public OncoKB refresh queued", `Task ${data.task_id || "queued"} will refresh the shared HGNC-matched reference collection.`, "Knowledgebases"),
    onError: (error) => notifyActionError("Unable to queue public OncoKB refresh", error, "Knowledgebases"),
  })

  const updateBool = (section: "celery" | "modules", key: string, value: boolean) => {
    const base = controls || controlsQuery.data?.controls
    if (!base) return
    setDraft({
      ...base,
      [section]: { ...base[section], [key]: value },
    })
  }

  const updateNumber = (key: string, value: string) => {
    const base = controls || controlsQuery.data?.controls
    if (!base) return
    const parsed = Number.parseInt(value, 10)
    setDraft({
      ...base,
      retention: { ...base.retention, [key]: Number.isFinite(parsed) ? parsed : 0 },
    })
  }

  const updateTiering = (key: string, value: boolean) => {
    const base = controls || controlsQuery.data?.controls
    if (!base) return
    setDraft({
      ...base,
      curation: {
        ...base.curation,
        tiering: { ...base.curation.tiering, [key]: value },
      },
    })
  }

  return (
    <PageShell
      eyebrow="Admin"
      title="Application Controls"
      description="Runtime switches for background workers, application modules, and operational retention policies."
      actions={
        <div className="flex flex-wrap gap-2">
          {canRunMaintenance && <Button type="button" variant="outline" onClick={() => runMaintenance.mutate()} disabled={runMaintenance.isPending || !controls?.celery?.enabled || !controls?.celery?.maintenance_enabled}>
            <RefreshCw className={`h-4 w-4 ${runMaintenance.isPending ? "animate-spin" : ""}`} />
            Run maintenance
          </Button>}
          {canRunMaintenance && <Button type="button" variant="outline" onClick={() => refreshPublicOncoKb.mutate()} disabled={refreshPublicOncoKb.isPending || !controls?.celery?.enabled || !controls?.celery?.maintenance_enabled || !controls?.modules?.knowledgebases_enabled}>
            <Database className={`h-4 w-4 ${refreshPublicOncoKb.isPending ? "animate-spin" : ""}`} />
            Refresh public OncoKB
          </Button>}
          {canEdit && <Button type="button" onClick={() => controls && saveControls.mutate(controls)} disabled={!controls || saveControls.isPending}>
            {saveControls.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save controls
          </Button>}
        </div>
      }
    >
      {controlsQuery.error ? (
        <ModuleNotice>{controlsQuery.error instanceof Error ? controlsQuery.error.message : "Unable to load application controls."}</ModuleNotice>
      ) : controlsQuery.isLoading || !controls ? (
        <section className="surface-panel">
          <AppLoader label="Loading controls" />
        </section>
      ) : (
        <div className="grid gap-3 xl:grid-cols-[1fr_1fr]">
          <ControlSection
            title="Celery Task Families"
            description="Sample ingestion is one complete clinical transaction. Generic collection writes and retention remain independent operational jobs."
            icon={<SlidersHorizontal className="h-4 w-4" />}
          >
            {Object.entries(controls.celery).map(([key, value]) => (
              <ControlToggle key={key} definition={appControlHelp(key)} checked={Boolean(value)} disabled={!canEdit} onChange={(checked) => updateBool("celery", key, checked)} />
            ))}
          </ControlSection>

          <ControlSection
            title="Application Modules"
            description="Disabling a module hides its UI routes and causes its API routes to return HTTP 503. Audit access remains permission-controlled."
            icon={<Settings2 className="h-4 w-4" />}
          >
            {Object.entries(controls.modules).map(([key, value]) => (
              <ControlToggle key={key} definition={appControlHelp(key)} checked={Boolean(value)} disabled={!canEdit} onChange={(checked) => updateBool("modules", key, checked)} />
            ))}
          </ControlSection>

          <ControlSection
            title="Clinical Curation"
            description="Resource-level availability of Tier 1-4 mutation actions. Existing classifications remain visible when an action is disabled."
            icon={<Tags className="h-4 w-4" />}
          >
            {Object.entries(controls.curation.tiering).map(([key, value]) => (
              <ControlToggle key={key} definition={appControlHelp(key)} checked={Boolean(value)} disabled={!canEdit} onChange={(checked) => updateTiering(key, checked)} />
            ))}
          </ControlSection>

          <section className="surface-panel p-3 xl:col-span-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Public OncoKB reference refresh</h2>
                <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                  Queues one background refresh of the public cancer-gene and curated-gene catalogues. The worker matches every remote record against approved, previous, and alias symbols in the local HGNC collection before updating shared reference records.
                </p>
              </div>
            </div>
          </section>

          <section className="surface-panel !overflow-visible p-3 xl:col-span-2">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Observed Runtime State</h2>
                <p className="text-sm text-muted-foreground">Live Celery process, queue, schedule, and repository health reported by the API runtime.</p>
                <p className="mt-1 flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
                  {runtime.observed_at
                    ? <TimeDisplay value={runtime.observed_at} prefix="Observed" />
                    : <span>Observation time was not reported.</span>}
                  <span>Automatically refreshed every 5 seconds; inspection timeout {runtime.celery?.inspection_timeout_seconds ?? 1.5} seconds.</span>
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => controlsQuery.refetch()} disabled={controlsQuery.isFetching}>
                  <RefreshCw className={`h-3.5 w-3.5 ${controlsQuery.isFetching ? "animate-spin" : ""}`} />
                  Refresh
                </Button>
                <RuntimeStatusBadge status={runtime.celery?.status} />
              </div>
            </div>
            <RuntimeExecutionSummary
              configuredEnabled={Boolean(runtime.celery?.configured_enabled)}
              executionState={runtime.celery?.execution_state}
              workersOnline={runtime.celery?.workers_online ?? 0}
            />
            <div className="mb-3 grid gap-3 lg:grid-cols-2">
              <EffectiveStatePanel
                title="Task-family gates"
                description="Effective gates checked by workers before application work starts."
                states={runtime.celery?.configured_families || {}}
              />
              <EffectiveStatePanel
                title="Application modules"
                description="Effective route availability enforced by both navigation and the API."
                states={Object.fromEntries(
                  Object.entries(runtime.modules || {}).map(([key, value]) => [
                    value.label || key,
                    Boolean(value.enabled),
                  ]),
                )}
              />
            </div>
            <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
              <RuntimeMetric label="Workers" value={runtime.celery?.workers_online ?? 0} description="Worker processes that responded to live inspection." />
              <RuntimeMetric label="Active" value={runtime.celery?.active_count ?? 0} description="Tasks currently executing across responding workers." />
              <RuntimeMetric label="Reserved" value={runtime.celery?.reserved_count ?? 0} description="Tasks fetched by workers but not yet executing." />
              <RuntimeMetric label="Scheduled" value={runtime.celery?.scheduled_count ?? 0} description="ETA or countdown tasks held by workers for later execution." />
              <RuntimeMetric label="Registered" value={runtime.celery?.registered_task_count ?? 0} description="Distinct task names known by responding workers." />
              <RuntimeMetric label="Beat entries" value={runtime.celery?.beat_schedule_count ?? 0} description="Periodic schedules configured in the API image. This does not prove that Beat is running." />
            </div>
            <div className="mt-3 grid gap-3 xl:grid-cols-2">
              <WorkerRuntimePanel workers={runtime.celery?.worker_details || []} />
              <BeatRuntimePanel entries={runtime.celery?.beat_entries || []} />
              <QueueRuntimePanel consumers={runtime.celery?.queue_consumers || {}} />
              <TaskRuntimePanel
                tasks={runtime.celery?.tasks || []}
                registeredTasks={runtime.celery?.registered_tasks || []}
              />
            </div>
            {runtime.celery?.error ? (
              <div className="mt-3 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
                Celery inspection did not complete: {runtime.celery.error}
              </div>
            ) : null}
            {runtime.index_setup_conflicts?.length ? (
              <div className="mt-3 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
                {runtime.index_setup_conflicts.length} Mongo index conflict(s) were tolerated at startup. Review the operations troubleshooting guide before changing indexes.
              </div>
            ) : null}
          </section>

          <section className="surface-panel !overflow-visible p-3 xl:col-span-2">
            <div className="mb-3">
              <h2 className="text-base font-semibold">Retention Policies</h2>
              <p className="text-sm text-muted-foreground">All values are days. Audit retention also updates the expiry horizon used when new audit events are written.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {Object.entries(controls.retention).map(([key, value]) => (
                <div key={key} className="rounded-xl border border-border bg-background/70 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <Label htmlFor={key} className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{appControlHelp(key).label}</Label>
                    <ControlHelp definition={appControlHelp(key)} />
                  </div>
                  <Input id={key} type="number" min={key === "audit_events_days" ? 30 : 1} value={String(value)} disabled={!canEdit} onChange={(event) => updateNumber(key, event.target.value)} />
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
              Last updated by <span className="font-semibold text-foreground">{controls.updated_by || "system defaults"}</span>
              {controls.updated_on && <TimeDisplay value={controls.updated_on} mode="full" prefix="on " className="ml-1" />}.
            </div>
          </section>
        </div>
      )}
    </PageShell>
  )
}

export function AdminAuditPage() {
  const [severity, setSeverity] = useState<Severity | "">("")
  const [category, setCategory] = useState("")
  const [actor, setActor] = useState("")
  const [search, setSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("7d")

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
  const columns = useMemo<ColumnDef<AuditEvent, any>[]>(() => [
    {
      id: "time",
      header: "Time",
      accessorFn: (event) => event.occurred_at ? new Date(event.occurred_at).getTime() : 0,
      cell: ({ row }) => (
        <span className="whitespace-nowrap">
          <TimeDisplay value={row.original.occurred_at} className="text-sm font-semibold" />
          <span className="block text-xs text-muted-foreground">
            {fullDateTime(row.original.occurred_at)}
          </span>
        </span>
      ),
      meta: {
        exportValue: (event: AuditEvent) => event.occurred_at ? new Date(event.occurred_at).toISOString() : "",
        cellClassName: "whitespace-nowrap",
      },
    },
    {
      id: "level",
      header: "Level",
      accessorFn: (event) => severityRank(severityValue(event.severity)),
      cell: ({ row }) => {
        const level = severityValue(row.original.severity)
        const Icon = severityIcon[level]
        return (
          <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-bold capitalize ${severityClass[level]}`}>
            <Icon className="h-3 w-3" /> {level}
          </span>
        )
      },
      meta: {
        exportValue: (event: AuditEvent) => severityValue(event.severity),
      },
    },
    {
      id: "event",
      header: "Event",
      accessorFn: (event) => `${event.message || ""} ${event.event_type || ""}`,
      cell: ({ row }) => (
        <div className="max-w-md">
          <div className="font-semibold text-foreground">{row.original.message || "-"}</div>
          <div className="mt-0.5 type-meta text-muted-foreground">{row.original.event_type || "-"}</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {(row.original.tags || []).slice(0, 4).map((tag) => (
              <span key={tag} className="rounded bg-muted px-1.5 py-0.5 type-label text-muted-foreground">{tag}</span>
            ))}
          </div>
        </div>
      ),
      meta: {
        exportValue: (event: AuditEvent) => `${event.message || ""} ${event.event_type || ""}`.trim(),
        cellClassName: "min-w-[260px]",
      },
    },
    {
      id: "actor",
      header: "Actor",
      accessorFn: (event) => event.actor?.username || event.actor?.fullname || "",
      cell: ({ row }) => {
        const roles = row.original.actor?.roles || []
        return (
          <div>
            <span className="block font-semibold">{row.original.actor?.fullname || row.original.actor?.username || "anonymous"}</span>
            <span className="block text-sm text-muted-foreground">{row.original.actor?.username || "-"}</span>
            {roles.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {roles.map((role) => <span key={role} className="rounded-full bg-primary/10 px-2 py-0.5 type-label font-bold text-primary">{role}</span>)}
              </div>
            )}
            {row.original.source?.client_ip && <span className="block type-meta text-muted-foreground">{row.original.source.client_ip}</span>}
          </div>
        )
      },
      meta: {
        exportValue: (event: AuditEvent) => event.actor?.username || event.actor?.fullname || "",
      },
    },
    {
      id: "resource",
      header: "Resource",
      accessorFn: (event) => `${event.resource?.type || ""} ${event.resource?.name || event.resource?.id || ""}`,
      cell: ({ row }) => {
        const resource = row.original.resource?.name || row.original.resource?.id
        return (
          <div>
            <span className="block text-sm font-semibold capitalize">{row.original.resource?.type?.replaceAll("_", " ") || "-"}</span>
            <span className="block max-w-48 truncate type-meta text-muted-foreground" title={resource || ""}>{resource || "-"}</span>
          </div>
        )
      },
      meta: {
        exportValue: (event: AuditEvent) => `${event.resource?.type || ""} ${event.resource?.name || event.resource?.id || ""}`.trim(),
      },
    },
    {
      id: "outcome",
      header: "Outcome",
      accessorFn: (event) => event.outcome || "unknown",
      cell: ({ row }) => (
        <span className="text-sm capitalize">{row.original.outcome || "unknown"}</span>
      ),
    },
    {
      id: "category",
      header: "Category",
      accessorFn: (event) => event.category || "",
      cell: ({ row }) => <span className="text-sm text-muted-foreground">{row.original.category || "uncategorized"}</span>,
    },
    {
      id: "context",
      header: "Context",
      enableSorting: false,
      cell: ({ row }) => (
        <details className="text-xs">
          <summary className="cursor-pointer text-primary">View details</summary>
          <div className="mt-2 w-80 space-y-1 rounded-lg bg-muted/60 p-2 type-meta">
            <Detail label="Request ID" value={row.original.source?.request_id} />
            <Detail label="Request" value={row.original.source?.method && row.original.source?.path ? `${row.original.source.method} ${row.original.source.path}` : null} />
            <Detail label="Resource name" value={row.original.resource?.name} />
            <Detail label="Resource ID" value={row.original.resource?.id} />
            <Detail label="Provider" value={row.original.actor?.provider} />
            <Detail label="Expires" value={row.original.expires_at ? localDate(row.original.expires_at) : null} />
            {row.original.metadata && Object.keys(row.original.metadata).length > 0 && (
              <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-background p-2">{JSON.stringify(row.original.metadata, null, 2)}</pre>
            )}
          </div>
        </details>
      ),
    },
  ], [])

  const clearFilters = () => {
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
                setSeverity(severity === level ? "" : level)
              }}
              className={`flex items-center justify-between rounded-xl border p-3 text-left transition-colors duration-100 ${severityClass[level]} ${severity === level ? "ring-2 ring-current ring-offset-2 ring-offset-background" : ""}`}
            >
              <span>
                <span className="block text-xs font-semibold uppercase tracking-wide">{level}</span>
                <span className="mt-0.5 block text-xl font-semibold type-numeric">{severityCounts[level]}</span>
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
              setActor(event.target.value)
            }}
            placeholder="Filter by username"
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
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

      <section className="surface-panel p-3">
        {error ? (
          <div className="p-4"><ModuleNotice>{error instanceof Error ? error.message : "Unable to load audit events."}</ModuleNotice></div>
        ) : isLoading ? (
          <AppLoader label="Loading audit events" />
        ) : (
          <DataTable
            columns={columns}
            data={filtered}
            filename="audit_events.csv"
            rowLabel="events"
            totalCount={filtered.length}
            hideSearch
            renderToolbar={() => (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                <Database className="h-3.5 w-3.5" />
                MongoDB audit_events
              </span>
            )}
          />
        )}
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

function severityRank(value: Severity) {
  return { info: 1, warning: 2, error: 3, critical: 4 }[value]
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="grid grid-cols-[5rem_1fr] gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all ">{value}</span>
    </div>
  )
}

export function AdminIngestPage() {
  const [yamlFile, setYamlFile] = useState<File | null>(null)
  const [dataArchive, setDataArchive] = useState<File | null>(null)
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
      if (dataArchive) formData.append("data_archive", dataArchive)
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
              <span className="text-xs font-semibold uppercase text-muted-foreground">YAML manifest</span>
              <input
                type="file"
                accept=".yaml,.yml"
                onChange={(event) => setYamlFile(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Referenced data archive</span>
              <input
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => setDataArchive(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              />
              <span className="block text-xs text-muted-foreground">
                Optional when the manifest paths are already readable. Otherwise upload one ZIP containing every declared data file.
              </span>
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
                <p className="text-xs font-semibold uppercase text-muted-foreground">Task ID</p>
                <p className="break-all text-sm">{taskId}</p>
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
      <p className="type-meta font-semibold uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  )
}
