import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { TimeDisplay } from "@/components/ui/time-display"
import {
  ADMIN_UTILITY_PERMISSIONS,
  hasPermission,
  useCurrentUserAccess,
} from "@/lib/access-control"
import { api } from "@/lib/api"
import { appControlHelp } from "@/lib/app-control-metadata"
import { APPLICATION_MODULES_QUERY_KEY } from "@/lib/app-module-state"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Activity,
  Database,
  RefreshCw,
  Save,
  Settings2,
  SlidersHorizontal,
  Tags
} from "lucide-react"
import { useState } from "react"

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

import { ModuleNotice } from "@/components/admin/ModuleNotice"

type AppControls = {
  email?: { enabled: boolean }
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

  const updateBool = (section: "celery" | "modules" | "email", key: string, value: boolean) => {
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
            title="Email Service"
            description="Control outgoing account, security, password-reset, and broadcast emails. In-app notifications remain available."
            icon={<Settings2 className="h-4 w-4" />}
          >
            <ControlToggle definition={appControlHelp("email_enabled")} checked={controls.email?.enabled ?? true} disabled={!canEdit} onChange={(checked) => updateBool("email", "enabled", checked)} />
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
