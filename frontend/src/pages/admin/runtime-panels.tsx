import type { ReactNode } from "react"
import { Activity, Info } from "lucide-react"
import { AppTooltip } from "@/components/ui/app-tooltip"
import type { AppControlHelp } from "@/lib/app-control-metadata"

type AppControlsRuntime = {
  celery?: {
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
    beat_entries?: { name?: string; task?: string; schedule?: string }[]
    tasks?: {
      worker?: string
      state?: string
      task_id?: string | null
      task_name?: string | null
      queue?: string | null
      eta?: string | null
      started_at?: number | string | null
    }[]
  }
}

export function EffectiveStatePanel({
  title,
  description,
  states,
}: {
  title: string
  description: string
  states: Record<string, boolean>
}) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(states).map(([key, enabled]) => (
          <span
            key={key}
            className={enabled
              ? "rounded-md border border-success/35 bg-success/10 px-2 py-1 text-xs font-bold text-success"
              : "rounded-md border border-warn/35 bg-warn/10 px-2 py-1 text-xs font-bold text-warn"
            }
          >
            {key.replaceAll("_", " ")}: {enabled ? "enabled" : "disabled"}
          </span>
        ))}
      </div>
    </div>
  )
}

export function RuntimeStatusBadge({ status }: { status?: string }) {
  const normalized = (status || "unknown").toLowerCase()
  const cls = normalized === "online"
    ? "border-success/40 bg-success/10 text-success"
    : normalized === "offline"
      ? "border-warn/40 bg-warn/10 text-warn"
      : "border-border bg-muted text-muted-foreground"
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-bold uppercase ${cls}`}>{normalized}</span>
}

export function RuntimeMetric({ label, value, description }: { label: string; value: number; description: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <InfoHint title={label} description={description} />
      </div>
      <p className="mt-1 text-lg font-black tabular-nums text-foreground">{value}</p>
    </div>
  )
}

export function RuntimeExecutionSummary({
  configuredEnabled,
  executionState,
  workersOnline,
}: {
  configuredEnabled: boolean
  executionState?: string
  workersOnline: number
}) {
  const state = executionState || "unknown"
  const content = state === "ready"
    ? {
        title: "Execution is allowed and workers are responding",
        detail: `${workersOnline} worker${workersOnline === 1 ? "" : "s"} can accept work, subject to each task-family gate.`,
        cls: "border-success/30 bg-success/10 text-success",
      }
    : state === "workers_missing"
      ? {
          title: "Execution is allowed, but no workers responded",
          detail: "Queued work cannot be confirmed as consumable. Check the worker container and broker connectivity.",
          cls: "border-warn/30 bg-warn/10 text-warn",
        }
      : state === "execution_disabled_workers_online"
        ? {
            title: "Application task execution is disabled",
            detail: `${workersOnline} worker${workersOnline === 1 ? " remains" : "s remain"} online, but controlled tasks will return without doing application work.`,
            cls: "border-warn/30 bg-warn/10 text-warn",
          }
        : state === "execution_disabled"
          ? {
              title: "Application task execution is disabled",
              detail: "No workers responded. The switch does not start or stop worker processes.",
              cls: "border-muted-foreground/20 bg-muted text-muted-foreground",
            }
          : {
              title: "Runtime execution state is unavailable",
              detail: configuredEnabled ? "The task gate is enabled, but live execution readiness could not be established." : "The task gate is disabled and live worker state could not be established.",
              cls: "border-warn/30 bg-warn/10 text-warn",
            }
  return (
    <div className={`mb-3 flex items-start gap-2 rounded-lg border p-3 ${content.cls}`}>
      <Activity className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="text-sm font-semibold">{content.title}</p>
        <p className="text-xs opacity-90">{content.detail}</p>
      </div>
    </div>
  )
}

export function WorkerRuntimePanel({ workers }: { workers: NonNullable<AppControlsRuntime["celery"]>["worker_details"] }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Worker details</p>
        <span className="text-xs text-muted-foreground">{workers?.length || 0} responding</span>
      </div>
      {workers?.length ? (
        <div className="grid gap-2">
          {workers.map((worker) => (
            <div key={worker.name} className="rounded-lg border border-border bg-card p-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-foreground">{worker.name}</span>
                <span className="rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[11px] font-bold uppercase text-success">{worker.status || "online"}</span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground sm:grid-cols-4">
                <span>Concurrency <strong className="text-foreground">{worker.concurrency ?? "-"}</strong></span>
                <span>Uptime <strong className="text-foreground">{formatDuration(worker.uptime_seconds)}</strong></span>
                <span>Processed <strong className="text-foreground">{worker.processed_count ?? 0}</strong></span>
                <span>PID <strong className="text-foreground">{worker.pid ?? "-"}</strong></span>
                <span>Active <strong className="text-foreground">{worker.active_count ?? 0}</strong></span>
                <span>Reserved <strong className="text-foreground">{worker.reserved_count ?? 0}</strong></span>
                <span>Scheduled <strong className="text-foreground">{worker.scheduled_count ?? 0}</strong></span>
                <span>Registered <strong className="text-foreground">{worker.registered_count ?? 0}</strong></span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">Queues: {(worker.queues || []).join(", ") || "none reported"}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No worker details were reported.</p>
      )}
    </div>
  )
}

export function BeatRuntimePanel({ entries }: { entries: NonNullable<AppControlsRuntime["celery"]>["beat_entries"] }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Periodic schedules</p>
        <InfoHint title="Periodic schedules" description="Schedules configured in the application image. Their presence does not prove that the separate Beat process is online." />
      </div>
      {entries?.length ? (
        <div className="grid gap-2">
          {entries.map((entry) => (
            <div key={entry.name} className="rounded-lg border border-border bg-card p-2.5">
              <p className="text-sm font-semibold text-foreground">{entry.name}</p>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">{entry.task || "Task not reported"}</p>
              <p className="mt-1 text-xs text-muted-foreground">Schedule: {entry.schedule || "not reported"}</p>
            </div>
          ))}
        </div>
      ) : <p className="text-sm text-muted-foreground">No periodic schedule entries are configured.</p>}
    </div>
  )
}

export function QueueRuntimePanel({ consumers }: { consumers: Record<string, string[]> }) {
  const entries = Object.entries(consumers)
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Queue consumers</p>
      {entries.length ? (
        <div className="grid gap-2">
          {entries.map(([queue, workers]) => (
            <div key={queue} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-2.5 py-2">
              <span className="font-mono text-xs font-bold text-foreground">{queue}</span>
              <span className="text-xs text-muted-foreground">{workers.join(", ")}</span>
            </div>
          ))}
        </div>
      ) : <p className="text-sm text-muted-foreground">No queues were reported by responding workers.</p>}
    </div>
  )
}

export function TaskRuntimePanel({
  tasks,
  registeredTasks,
}: {
  tasks: NonNullable<AppControlsRuntime["celery"]>["tasks"]
  registeredTasks: string[]
}) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Task activity and capabilities</p>
      {tasks?.length ? (
        <div className="mb-3 grid gap-2">
          {tasks.map((task, index) => (
            <div key={`${task.state}-${task.task_id || task.task_name || index}`} className="rounded-lg border border-border bg-card p-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono font-bold text-foreground">{task.task_name || "Unnamed task"}</span>
                <span className="rounded-full border border-border bg-muted px-2 py-0.5 font-bold uppercase text-muted-foreground">{task.state}</span>
              </div>
              <p className="mt-1 text-muted-foreground">Worker {task.worker || "-"} · Queue {task.queue || "-"} · ID {task.task_id || "-"}</p>
            </div>
          ))}
        </div>
      ) : <p className="mb-3 text-sm text-muted-foreground">No active, reserved, or scheduled tasks were observed.</p>}
      <details>
        <summary className="cursor-pointer text-xs font-semibold text-link">Show {registeredTasks.length} registered task names</summary>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {registeredTasks.map((task) => <span key={task} className="rounded-md border border-border bg-card px-2 py-1 font-mono text-[11px] text-muted-foreground">{task}</span>)}
        </div>
      </details>
    </div>
  )
}

function formatDuration(seconds?: number | null) {
  if (!Number.isFinite(seconds)) return "-"
  const total = Math.max(0, Number(seconds))
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3_600)
  const minutes = Math.floor((total % 3_600) / 60)
  if (days) return `${days}d ${hours}h`
  if (hours) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export function ControlSection({ title, description, icon, children }: { title: string; description: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="surface-panel !overflow-visible p-3">
      <div className="mb-3 flex items-start gap-2">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">{icon}</div>
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="grid gap-2">{children}</div>
    </section>
  )
}

export function InfoHint({ title, description }: { title: string; description: string }) {
  return (
    <AppTooltip context="More information" label={title} content={description}>
      <button
        type="button"
        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`About ${title}`}
      >
        <Info className="h-3.5 w-3.5" />
      </button>
    </AppTooltip>
  )
}

export function ControlHelp({ definition }: { definition: AppControlHelp }) {
  const content = `${definition.summary} Enabled: ${definition.enabledEffect} Disabled: ${definition.disabledEffect} Operational note: ${definition.operationalNote}`
  return (
    <AppTooltip context="Application control" label={definition.label} content={content} persistOnClick>
      <button
        type="button"
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`About ${definition.label}`}
      >
        <Info className="h-3.5 w-3.5" />
      </button>
    </AppTooltip>
  )
}

export function ControlToggle({ definition, checked, onChange, disabled = false }: { definition: AppControlHelp; checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/70 px-3 py-2">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-foreground">{definition.label}</p>
        <p className="truncate text-xs text-muted-foreground">{definition.summary}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <ControlHelp definition={definition} />
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          aria-label={`${definition.label}: ${checked ? "enabled" : "disabled"}`}
          disabled={disabled}
          onClick={() => onChange(!checked)}
          className={`relative h-6 w-11 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 ${checked ? "border-primary bg-primary" : "border-border bg-muted"}`}
        >
          <span className={`absolute top-0.5 h-[1.125rem] w-[1.125rem] rounded-full bg-white shadow-sm transition-transform ${checked ? "left-[1.35rem]" : "left-0.5"}`} />
        </button>
      </div>
    </div>
  )
}
