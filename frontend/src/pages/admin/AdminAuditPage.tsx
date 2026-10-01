import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { TimeDisplay } from "@/components/ui/time-display"
import { api } from "@/lib/api"
import { fullDateTime, localDate } from "@/lib/detail-formatters"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import {
  AlertTriangle,
  CircleAlert,
  Database,
  Info,
  RefreshCw,
  Search,
  Siren
} from "lucide-react"
import { useMemo, useState } from "react"


import { ModuleNotice } from "@/components/admin/ModuleNotice"

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
