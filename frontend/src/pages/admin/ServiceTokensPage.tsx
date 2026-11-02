import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import type { PersonalTokenCreate, ServiceTokenCreate, ServiceTokenIssued, ServiceTokenList, ServiceTokenMetadata, ServiceTokenOptions } from "@/lib/generated"
import { useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { AdminHomeLink } from "./AdminHomeLink"

const operationLabels = {
  sample_bundle: "Submit a sample manifest",
  sample_upload: "Upload a sample bundle",
  sample_bundle_async: "Submit a background sample manifest",
  sample_upload_async: "Upload a background sample bundle",
  job_status: "Read status and results of jobs submitted with this token",
} as const
type Operation = keyof typeof operationLabels

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
    { accessorKey: "name", header: "Name" },
    { accessorKey: "owner", header: "Owner" },
    { accessorKey: "kind", header: "Type" },
    { id: "operations", header: "Operations", accessorFn: row => row.operations.map(operation => operationLabels[operation]).join(", ") },
    { id: "scope", header: "Scope", accessorFn: row => `${row.asp_ids.join(", ")} · ${row.environments.join(", ")}` },
    { id: "status", header: "Status", accessorFn: row => row.revoked_at ? "Revoked" : new Date(row.expires_at) <= new Date() ? "Expired" : "Active" },
    { id: "expiry", header: "Expires", accessorFn: row => new Date(row.expires_at).toLocaleString() },
    { id: "last_used", header: "Last used", accessorFn: row => row.last_used_at ? new Date(row.last_used_at).toLocaleString() : "Never" },
    { id: "actions", header: "Actions", cell: ({ row }) => <Button aria-label={`Revoke ${row.original.name}`} size="sm" variant="destructive" disabled={!!row.original.revoked_at} onClick={() => setRevoking(row.original)}>Revoke</Button> },
  ]

  return <PageShell eyebrow={personal ? "My account" : "Administration"} title={personal ? "Access tokens" : "Service tokens"} description={personal ? "Manage personal ingestion credentials bounded by your current account access." : "Create scoped credentials for unattended sample ingestion."} actions={personal ? <Link to="/profile" className="paper-raised-control rounded-lg px-3 py-2 type-body">My account</Link> : <AdminHomeLink />}>
    {issued && <section role="status" className="glass-card space-y-3 p-4">
      <h2 className="type-section-title">Save this token now</h2>
      <p className="type-body">This secret is shown once. Send it using the Authorization: Bearer header. Store it in your pipeline’s secret store.</p>
      <Input aria-label={personal ? "New personal token" : "New service token"} readOnly value={issued.token} autoComplete="off" />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { void navigator.clipboard.writeText(issued.token).then(() => notifySuccess("Token copied"), error => notifyActionError("Unable to copy token", error)) }}>Copy token</Button>
        <Button variant="outline" onClick={() => { setIssued(null); create.reset() }}>Dismiss secret</Button>
      </div>
    </section>}
    <form className="glass-card space-y-4 p-4" onSubmit={event => {
      event.preventDefault()
      create.mutate({ name: name.trim(), ...(personal ? {} : { owner }), expires_hours: hours, operations, asp_ids: assays, environments })
    }}>
      <h2 className="type-section-title">{personal ? "Create a personal token" : "Create a service token"}</h2>
      <p className="type-body text-muted-foreground">{personal ? "Personal tokens act on your behalf and remain limited by your current permissions and scopes. " : "Tokens use a named automation identity. "}Choose ingestion and job-status operations explicitly. Tokens cannot access reports, perform clinical review or import collections. Disabling the owner also disables their tokens.</p>
      {options.isPending && <p role="status">Loading available owners and scopes…</p>}
      {personal && options.data && !options.data.operations.length && <p className="type-body text-muted-foreground">Your account currently has no supported ingestion permissions. You can still revoke your existing tokens below.</p>}
      {options.isError && <p role="alert">Unable to load token options. <Button type="button" variant="outline" onClick={() => void options.refetch()}>Retry</Button></p>}
      <div className="grid gap-4 md:grid-cols-3">
        <label className="type-label">Name<Input required maxLength={100} value={name} onChange={event => setName(event.target.value)} placeholder="Sequencing pipeline" /></label>
        {!personal && <label className="type-label">Owner<select aria-label="Owner" required className="paper-inset form-control w-full rounded-lg px-2 py-1" value={owner} onChange={event => setOwner(event.target.value)}><option value="">Select an owner</option>{options.data?.owners.map(user => <option key={user.username} value={user.username}>{user.name} ({user.username})</option>)}</select></label>}
        <label className="type-label">Lifetime (hours)<Input required type="number" min={1} max={8760} value={hours} onChange={event => setHours(Number(event.target.value))} /></label>
      </div>
      <fieldset className="space-y-2"><legend className="type-label">Allowed operations</legend>{options.data?.operations.map(operation => <label key={operation} className="flex items-center gap-2 type-body"><input type="checkbox" checked={operations.includes(operation)} onChange={event => setOperations(current => event.target.checked ? [...current, operation] : current.filter(value => value !== operation))} />{operationLabels[operation]}</label>)}</fieldset>
      <div className="grid gap-4 md:grid-cols-2">
        <fieldset className="space-y-2"><legend className="type-label">Allowed assays</legend><div className="max-h-52 space-y-2 overflow-y-auto">{options.data?.assays.map(assay => <label key={assay.asp_id} className="flex items-center gap-2 type-body"><input type="checkbox" checked={assays.includes(assay.asp_id)} onChange={event => setAssays(current => event.target.checked ? [...current, assay.asp_id] : current.filter(value => value !== assay.asp_id))} />{assay.name} ({assay.asp_id})</label>)}</div></fieldset>
        <fieldset className="space-y-2"><legend className="type-label">Allowed clinical environments</legend>{options.data?.environments.map(environment => <label key={environment} className="flex items-center gap-2 type-body"><input type="checkbox" checked={environments.includes(environment)} onChange={event => setEnvironments(current => event.target.checked ? [...current, environment] : current.filter(value => value !== environment))} />{environment}</label>)}</fieldset>
      </div>
      <Button type="submit" disabled={create.isPending || !!issued || !options.data || !name.trim() || (!personal && !owner) || !operations.length || operations.some(operation => !options.data?.operations.includes(operation)) || !assays.length || !environments.length}>Create token</Button>
    </form>
    <section className="glass-card p-4">
      <h2 className="type-section-title mb-3">{personal ? "Your tokens" : "Managed tokens"}</h2>
      {tokens.isPending ? <p role="status">Loading tokens…</p> : tokens.isError ? <p role="alert">Unable to load tokens. <Button variant="outline" onClick={() => void tokens.refetch()}>Retry</Button></p> : <DataTable columns={columns} data={tokens.data?.items || []} filename={personal ? "personal-token-metadata.csv" : "service-token-metadata.csv"} />}
    </section>
    <ConfirmationDialog open={!!revoking} title={personal ? "Revoke personal token?" : "Revoke service token?"} description={`Future requests using ${revoking?.name || "this token"} will be rejected. Work already in progress may complete.`} confirmLabel="Revoke token" variant="destructive" isPending={revoke.isPending} onCancel={() => setRevoking(null)} onConfirm={() => { if (revoking) revoke.mutate(revoking.token_id) }} />
  </PageShell>
}
