import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Input } from "@/components/ui/input"
import { SearchInput } from "@/components/ui/search-input"
import { icon } from "@/lib/assets"
import { api } from "@/lib/api"
import type { PersonalTokenCreate, ServiceTokenCreate, ServiceTokenIssued, ServiceTokenList, ServiceTokenMetadata, ServiceTokenOptions } from "@/lib/generated"
import { useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { cn } from "@/lib/utils"
import { AdminHomeLink } from "./AdminHomeLink"

const operationLabels = {
  sample_bundle: "Submit a sample manifest",
  sample_upload: "Upload a sample bundle",
  sample_bundle_async: "Submit a background sample manifest",
  sample_upload_async: "Upload a background sample bundle",
  job_status: "Read status and results of jobs submitted with this token",
} as const
type Operation = keyof typeof operationLabels

const operationDescriptions: Record<Operation, string> = {
  sample_bundle: "Process a JSON sample manifest immediately.",
  sample_upload: "Process an uploaded sample bundle immediately.",
  sample_bundle_async: "Queue a JSON sample manifest for background processing.",
  sample_upload_async: "Queue an uploaded sample bundle for background processing.",
  job_status: "Check progress and retrieve results for this token’s jobs.",
}

function ScopePicker({ title, items, selected, onChange, searchable = false }: {
  title: string
  items: { value: string; label: string; detail?: string }[]
  selected: string[]
  onChange: (values: string[]) => void
  searchable?: boolean
}) {
  const [search, setSearch] = useState("")
  const visible = items.filter(item => `${item.label} ${item.value}`.toLowerCase().includes(search.toLowerCase()))
  return <fieldset className="paper-inset min-w-0 rounded-xl border border-border/60 p-4">
    <legend className="px-1 type-label">{title}</legend>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <span className="type-body-sm text-muted-foreground">Choose the scope this token can access.</span>
      <Badge variant="secondary">{selected.length} selected</Badge>
    </div>
    {searchable && <SearchInput aria-label={`Search ${title.toLowerCase()}`} placeholder="Search by name or ID…" value={search} onChange={event => setSearch(event.target.value)} className="mb-3 max-w-none" />}
    <div className="max-h-60 space-y-1 overflow-y-auto overscroll-contain p-1">
      {visible.map(item => <label key={item.value} className={cn("flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 transition-colors focus-within:ring-2 focus-within:ring-ring", selected.includes(item.value) ? "border-primary/40 bg-primary/5" : "border-transparent hover:bg-muted/60")}>
        <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-primary" aria-label={item.detail ? `${item.label} (${item.detail})` : item.label} checked={selected.includes(item.value)} onChange={event => onChange(event.target.checked ? [...selected, item.value] : selected.filter(value => value !== item.value))} />
        <span className="min-w-0 type-body-sm"><span className="block break-words text-foreground">{item.label}</span>{item.detail && <span className="block break-all type-meta text-muted-foreground">{item.detail}</span>}</span>
      </label>)}
      {!visible.length && <p className="py-3 type-body-sm text-muted-foreground">{search ? "No matching scopes. Try another name or ID." : "No scopes available for this account."}</p>}
    </div>
  </fieldset>
}

export function ServiceTokensPage({ personal = false }: { personal?: boolean }) {
  const access = useCurrentUserAccess()
  const endpoint = personal ? "/auth/personal-tokens" : "/admin/service-tokens"
  const queryKey = ["managed-tokens", personal ? "personal" : "admin", access.data?.username]
  const client = useQueryClient()
  const [name, setName] = useState("")
  const [owner, setOwner] = useState("")
  const [hours, setHours] = useState(720)
  const [operations, setOperations] = useState<Operation[]>(personal ? [] : ["sample_upload"])
  const [assays, setAssays] = useState<string[]>([])
  const [environments, setEnvironments] = useState<string[]>([])
  const [issued, setIssued] = useState<ServiceTokenIssued | null>(null)
  const [revoking, setRevoking] = useState<ServiceTokenMetadata | null>(null)
  const options = useQuery({ queryKey: [...queryKey, "options"], queryFn: () => api.get<ServiceTokenOptions>(`${endpoint}/options`).then(response => response.data) })
  const tokens = useQuery({ queryKey, queryFn: () => api.get<ServiceTokenList>(endpoint).then(response => response.data) })
  const create = useMutation({
    gcTime: 0,
    mutationFn: (payload: ServiceTokenCreate | PersonalTokenCreate) => api.post<ServiceTokenIssued>(endpoint, payload).then(response => response.data),
    onSuccess: result => { setIssued(result); setName(""); void client.invalidateQueries({ queryKey, exact: true }) },
    onError: error => notifyActionError(`Unable to create ${personal ? "personal" : "service"} token`, error),
  })
  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`${endpoint}/${encodeURIComponent(id)}`),
    onSuccess: () => {
      if (issued?.metadata.token_id === revoking?.token_id) setIssued(null)
      setRevoking(null)
      void client.invalidateQueries({ queryKey, exact: true })
      notifySuccess(personal ? "Personal token revoked" : "Service token revoked")
    },
    onError: error => notifyActionError("Unable to revoke token", error),
  })
  const columns: ColumnDef<ServiceTokenMetadata>[] = [
    { accessorKey: "name", header: "Name", cell: ({ row }) => <span className="flex items-center gap-2 font-medium"><icon.keyRound className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />{row.original.name}</span> },
    { accessorKey: "owner", header: "Owner" },
    { accessorKey: "kind", header: "Type" },
    { id: "operations", header: "Operations", accessorFn: row => row.operations.map(operation => operationLabels[operation]).join(", "), cell: ({ row }) => <div className="flex flex-wrap gap-1.5">{row.original.operations.map(operation => <Badge key={operation} variant="outline" className="whitespace-normal text-left">{operationLabels[operation]}</Badge>)}</div> },
    { id: "scope", header: "Scope", accessorFn: row => `${row.asp_ids.join(", ")} · ${row.environments.join(", ")}` },
    { id: "status", header: "Status", accessorFn: row => row.revoked_at ? "Revoked" : new Date(row.expires_at) <= new Date() ? "Expired" : "Active", cell: ({ getValue }) => <Badge variant={getValue() === "Active" ? "secondary" : "outline"}>{String(getValue())}</Badge> },
    { id: "expiry", header: "Expires", accessorFn: row => new Date(row.expires_at).toLocaleString() },
    { id: "last_used", header: "Last used", accessorFn: row => row.last_used_at ? new Date(row.last_used_at).toLocaleString() : "Never" },
    { id: "actions", header: "Actions", cell: ({ row }) => <Button aria-label={`Revoke ${row.original.name}`} size="sm" variant="destructive" disabled={!!row.original.revoked_at} onClick={() => setRevoking(row.original)}>Revoke</Button> },
  ]

  return <PageShell eyebrow={personal ? "My account" : "Administration"} title={personal ? "Access tokens" : "Service tokens"} description={personal ? "Manage personal ingestion credentials bounded by your current account access." : "Create scoped credentials for unattended sample ingestion."} actions={personal ? <Link to="/profile" className="paper-raised-control rounded-lg px-3 py-2 type-body">My account</Link> : <AdminHomeLink />}>
    {issued && <section role="status" className="glass-card space-y-4 border-primary/40 p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-primary/10 p-2.5 text-primary"><icon.keyRound className="size-5" aria-hidden="true" /></div>
        <div><h2 className="type-card-title">Save this token now</h2><p className="mt-1 type-body-sm text-muted-foreground">This secret is shown once. Store it in your pipeline’s secret store.</p></div>
      </div>
      <Input className="font-mono" aria-label={personal ? "New personal token" : "New service token"} readOnly value={issued.token} autoComplete="off" spellCheck={false} />
      <p className="type-body-sm text-muted-foreground">Send it in the <code>Authorization: Bearer &lt;token&gt;</code> request header.</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { void navigator.clipboard.writeText(issued.token).then(() => notifySuccess("Token copied"), error => notifyActionError("Unable to copy token", error)) }}><icon.copy className="size-4" aria-hidden="true" />Copy token</Button>
        <Button variant="outline" onClick={() => { setIssued(null); create.reset() }}>Dismiss secret</Button>
      </div>
    </section>}
    <form className="glass-card min-w-0" onSubmit={event => {
      event.preventDefault()
      create.mutate({ name: name.trim(), ...(personal ? {} : { owner }), expires_hours: hours, operations, asp_ids: assays, environments })
    }}>
      <div className="flex items-start gap-3 border-b border-border/60 p-5 sm:p-6">
        <div className="rounded-xl bg-primary/10 p-2.5 text-primary"><icon.shieldCheck className="size-5" aria-hidden="true" /></div>
        <div className="min-w-0"><h2 className="type-card-title">{personal ? "Create a personal token" : "Create a service token"}</h2><p className="mt-1 max-w-3xl type-body-sm text-muted-foreground">{personal ? "Connect a script or pipeline using your current account access." : "Give a pipeline its own credential, owner and access scope."} Choose exactly what it can do and where it can ingest.</p></div>
      </div>
      <div className="space-y-5 p-5 sm:p-6">
      {options.isPending && <p role="status">Loading available owners and scopes…</p>}
      {personal && options.data && !options.data.operations.length && <p className="type-body text-muted-foreground">Your account currently has no supported ingestion permissions. You can still revoke your existing tokens below.</p>}
      {options.isError && <p role="alert">Unable to load token options. <Button type="button" variant="outline" onClick={() => void options.refetch()}>Retry</Button></p>}
      <div className={cn("grid gap-4", personal ? "sm:grid-cols-2" : "md:grid-cols-3")}>
        <div><label className="mb-2 block type-label" htmlFor="token-name">Name</label><Input id="token-name" required maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Sequencing pipeline" /><p className="mt-2 type-meta text-muted-foreground">A recognizable name for this script or integration.</p></div>
        {!personal && <div><label htmlFor="token-owner" className="mb-2 block type-label">Owner</label><select id="token-owner" required className="form-control w-full rounded-lg px-3 py-2 type-body" value={owner} onChange={event => setOwner(event.target.value)}><option value="">Select an owner</option>{options.data?.owners.map(user => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select><p className="mt-2 type-meta text-muted-foreground">Disabling this account also disables its tokens.</p></div>}
        <div><label htmlFor="token-hours" className="mb-2 block type-label">Lifetime (hours)</label><Input id="token-hours" required type="number" min={1} max={8760} value={hours} onChange={event => setHours(Number(event.target.value))} /><p className="mt-2 type-meta text-muted-foreground">Expires automatically. Up to 8,760 hours (one year).</p></div>
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <fieldset className="min-w-0 space-y-3"><legend className="mb-1 type-label">Allowed operations</legend><p className="type-body-sm text-muted-foreground">Enable only the requests this integration needs.</p>{options.data?.operations.map(operation => <label key={operation} className={cn("paper-inset flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-ring", operations.includes(operation) ? "border-primary/40 bg-primary/5" : "border-border/60 hover:border-primary/30")}>
          <input type="checkbox" className="mt-0.5 size-4 shrink-0 accent-primary" aria-label={operationLabels[operation]} checked={operations.includes(operation)} onChange={event => setOperations(current => event.target.checked ? [...current, operation] : current.filter(value => value !== operation))} />
          <span className="min-w-0"><span className="block type-body-sm font-medium">{operationLabels[operation]}</span><span className="mt-1 block type-meta text-muted-foreground">{operationDescriptions[operation]}</span></span>
        </label>)}</fieldset>
        <div className="min-w-0 space-y-4">
          <ScopePicker title="Allowed assays" searchable items={options.data?.assays.map(assay => ({ value: assay.asp_id, label: assay.name, detail: assay.asp_id })) || []} selected={assays} onChange={setAssays} />
          <ScopePicker title="Allowed clinical environments" items={options.data?.environments.map(environment => ({ value: environment, label: environment })) || []} selected={environments} onChange={setEnvironments} />
        </div>
      </div>
      <div className="paper-inset flex items-start gap-3 rounded-xl border border-border/60 p-4 type-body-sm text-muted-foreground"><icon.shield className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" /><p>{personal ? "Personal tokens remain limited by your current permissions and scopes. " : "Service tokens use the selected owner account. "}Tokens cannot access reports, perform clinical review or import collections. Disabling the owner also disables their tokens.</p></div>
      </div>
      <div className="flex flex-col gap-3 border-t border-border/60 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p className="type-body-sm text-muted-foreground">Operations: {operations.length} · Assays: {assays.length} · Environments: {environments.length}</p>
        <Button type="submit" disabled={create.isPending || !!issued || !options.data || !name.trim() || (!personal && !owner) || !operations.length || operations.some(operation => !options.data?.operations.includes(operation)) || !assays.length || !environments.length}><icon.plus className="size-4" aria-hidden="true" />{create.isPending ? "Creating token…" : "Create token"}</Button>
      </div>
    </form>
    <section className="glass-card min-w-0 p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h2 className="type-card-title">{personal ? "Your tokens" : "Managed tokens"}</h2><p className="mt-1 type-body-sm text-muted-foreground">Review access, expiry and recent use. Revoke credentials you no longer need.</p></div>{tokens.data && <Badge variant="secondary">{tokens.data.items.length} total</Badge>}</div>
      {tokens.isPending ? <p role="status">Loading tokens…</p> : tokens.isError ? <p role="alert">Unable to load tokens. <Button variant="outline" onClick={() => void tokens.refetch()}>Retry</Button></p> : <DataTable columns={columns} data={tokens.data?.items || []} emptyMessage="No tokens yet. Create one above to connect a script or pipeline." filename={personal ? "personal-token-metadata.csv" : "service-token-metadata.csv"} />}
    </section>
    <ConfirmationDialog open={!!revoking} title={personal ? "Revoke personal token?" : "Revoke service token?"} description={`Future requests using ${revoking?.name || "this token"} will be rejected. Work already in progress may complete.`} confirmLabel="Revoke token" variant="destructive" isPending={revoke.isPending} onCancel={() => setRevoking(null)} onConfirm={() => { if (revoking) revoke.mutate(revoking.token_id) }} />
  </PageShell>
}
