import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Link } from "react-router-dom"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { Button } from "@/components/ui/button"
import { TableBadge } from "@/components/ui/table-badge"
import { SearchInput } from "@/components/ui/search-input"
import { TimeDisplay } from "@/components/ui/time-display"
import { api } from "@/lib/api"
import { icon } from "@/lib/assets"

type IngestionEvent = {
  _id: string
  occurred_at: string
  event_type: string
  message: string
  outcome: string
  actor?: { username?: string }
  resource?: { type?: string; id?: string; name?: string }
  source?: { request_id?: string; path?: string; environment?: string }
  tags?: string[]
  metadata?: Record<string, unknown>
}
type AuditResponse = { events: IngestionEvent[]; total: number }

function stage(event: IngestionEvent): string {
  if (event.event_type.endsWith(".unconfirmed")) return "Needs reconciliation"
  if (event.event_type.endsWith(".started")) return "Started"
  if (event.event_type.endsWith(".succeeded")) return "Succeeded"
  if (event.outcome === "denied") return "Denied"
  if (event.outcome === "failure") return "Failed"
  return "Information"
}

function origin(event: IngestionEvent): string {
  if (event.event_type.startsWith("ingest.watch.")) return "Folder watcher"
  if (event.tags?.includes("celery")) return "Celery"
  return String(event.metadata?.source || "API")
}

function correlation(event: IngestionEvent): string {
  return String(event.metadata?.attempt_id || event.metadata?.task_id || event.source?.request_id || event._id)
}

function Outcome({ event }: { event: IngestionEvent }) {
  const label = stage(event)
  const tone = label === "Succeeded" ? "border-pass/50 bg-pass/10 text-pass"
    : label === "Failed" || label === "Denied" ? "border-destructive/50 bg-destructive/10 text-destructive"
      : label === "Needs reconciliation" ? "badge-warning"
        : "border-primary/30 bg-primary/10 text-primary"
  return <TableBadge className={`rounded-full font-semibold ${tone}`}>{label}</TableBadge>
}

export function AdminIngestionAuditPage() {
  const [search, setSearch] = useState("")
  const [outcome, setOutcome] = useState("")
  const [source, setSource] = useState("")
  const [selected, setSelected] = useState<IngestionEvent | null>(null)
  const detailsRef = useRef<HTMLElement>(null)
  useEffect(() => { if (selected) detailsRef.current?.focus() }, [selected])
  const query = useQuery<AuditResponse>({
    queryKey: ["admin-ingestion-audit"],
    queryFn: () => api.get("/admin/audit?ingestion_only=true&limit=1000").then((res) => res.data),
    refetchInterval: 30_000,
    retry: false,
  })
  const events = useMemo(() => query.data?.events || [], [query.data])
  const visible = useMemo(() => events.filter((event) => {
    if (outcome && stage(event) !== outcome) return false
    if (source && origin(event) !== source) return false
    const text = [event.message, event.event_type, event.actor?.username,
      event.resource?.name, event.resource?.id, event.metadata?.manifest,
      event.metadata?.error, correlation(event)].join(" ").toLowerCase()
    return text.includes(search.trim().toLowerCase())
  }), [events, outcome, source, search])
  const history = selected ? events.filter((event) => correlation(event) === correlation(selected)) : []
  const columns: ColumnDef<IngestionEvent>[] = [
    { id: "time", header: "Time", accessorKey: "occurred_at",
      cell: ({ row }) => <TimeDisplay value={row.original.occurred_at} /> },
    { id: "outcome", header: "Outcome", accessorFn: stage,
      cell: ({ row }) => <Outcome event={row.original} /> },
    { id: "sample", header: "Sample / manifest", accessorFn: (event) => event.resource?.name || String(event.metadata?.manifest || ""),
      cell: ({ row }) => {
        const event = row.original
        return <div className="max-w-sm break-words">
          {event.resource?.type === "sample" && event.resource.id
            ? <Link className="font-semibold text-primary underline" to={`/samples/${encodeURIComponent(event.resource.id)}`}>{event.resource.name || event.resource.id}</Link>
            : <span>{String(event.metadata?.manifest || "No sample assigned")}</span>}
          <p className="type-meta text-muted-foreground">{event.message}</p>
        </div>
      } },
    { id: "source", header: "Source", accessorFn: origin },
    { id: "actor", header: "Submitted by", accessorFn: (event) => event.actor?.username || "System" },
    { id: "duration", header: "Duration", accessorFn: (event) => typeof event.metadata?.duration_ms === "number" ? `${(event.metadata.duration_ms / 1000).toFixed(1)} s` : "—" },
    { id: "details", header: "Details", enableSorting: false,
      cell: ({ row }) => <Button variant="outline" size="sm" onClick={() => setSelected(row.original)} aria-label={`Inspect ${row.original.message}`}>Inspect</Button> },
  ]
  return <PageShell eyebrow="Admin" title="Ingestion audit"
    description="Trace ingestion attempts, outcomes and recovery details across API uploads and workers."
    actions={<Button variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}><icon.refreshCw className="h-4 w-4" /> Refresh</Button>}>
    {query.isLoading ? <AppLoader /> : query.error ? <div role="alert" className="glass-card p-4 text-destructive">Unable to load ingestion audit. Use Refresh to retry.</div> : <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {["All events", "Succeeded", "Failed", "Needs reconciliation"].map((label) => <button
          key={label} type="button" aria-pressed={outcome === (label === "All events" ? "" : label)}
          className={`glass-card p-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${outcome === (label === "All events" ? "" : label) ? "border-primary" : ""}`}
          onClick={() => setOutcome(label === "All events" ? "" : label)}>
          <span className="type-label text-muted-foreground">{label}</span>
          <strong className="block text-2xl font-semibold tabular-nums">{label === "All events" ? events.length : events.filter((event) => stage(event) === label).length}</strong>
          <span className="type-meta text-muted-foreground">In the loaded event window</span>
        </button>)}
      </div>
      <section className="glass-card space-y-4 p-4" aria-label="Ingestion events">
        <div className="flex flex-wrap items-end gap-3">
          <SearchInput aria-label="Search ingestion events" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Sample, manifest, actor, error or attempt ID…" />
          <label className="type-label">Outcome<select aria-label="Outcome" className="form-control mt-1 block h-9 rounded-lg px-3 type-body" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
            <option value="">All outcomes</option>{["Started", "Succeeded", "Failed", "Denied", "Needs reconciliation", "Information"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <label className="type-label">Source<select aria-label="Source" className="form-control mt-1 block h-9 rounded-lg px-3 type-body" value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">All sources</option>{Array.from(new Set(events.map(origin))).sort().map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <Button variant="ghost" onClick={() => { setSearch(""); setOutcome(""); setSource("") }}>Clear filters</Button>
        </div>
        <p className="type-meta text-muted-foreground">{events.length} latest events loaded of {query.data?.total ?? events.length}. Filters and counts apply to this window. Updates every 30 seconds.</p>
        <DataTable columns={columns} data={visible} filename="ingestion-audit.csv" hideSearch />
        {!events.length && <p className="text-muted-foreground">No ingestion events have been recorded yet.</p>}
      </section>
      {selected && <section ref={detailsRef} tabIndex={-1} className="glass-card space-y-3 p-4 focus-visible:outline focus-visible:outline-primary" aria-label="Ingestion attempt details">
        <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Attempt details</h2><Button variant="ghost" onClick={() => setSelected(null)}>Close details</Button></div>
        <p className="break-all type-meta text-muted-foreground">Correlation: {correlation(selected)}</p>
        <p className="type-meta text-muted-foreground">Recorded events are not a live job status. A start without a terminal event does not prove the job is still running. History below is limited to loaded events.</p>
        <ol className="space-y-3">{history.slice().reverse().map((event) => <li key={event._id} className="rounded-lg border border-border bg-muted/30 p-3">
          <div className="flex flex-wrap items-center gap-2"><Outcome event={event} /><TimeDisplay value={event.occurred_at} /><span className="type-meta text-muted-foreground">{event.actor?.username || "System"}</span></div>
          <p className="mt-2 break-words">{event.message}</p>
          {event.metadata?.error != null && <p className="mt-2 whitespace-pre-wrap break-words text-destructive">{String(event.metadata.error)}</p>}
          <details className="mt-2"><summary className="cursor-pointer text-primary">Technical context</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 type-meta">{JSON.stringify({ event: event.event_type, source: event.source, metadata: event.metadata }, null, 2)}</pre></details>
        </li>)}</ol>
      </section>}
    </>}
  </PageShell>
}
