import { useId, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Power, Save, X } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { StatusBadge } from "@/pages/admin/resource-list"
import { RecordProvenance } from "./RecordProvenance"
import { AdminHomeLink } from "./AdminHomeLink"
import type { RecordProvenanceData } from "./record-provenance"

type Group = RecordProvenanceData & { group_id: string; display_name: string; description: string; system_managed: boolean; is_active: boolean; version: number }
const empty = { group_id: "", display_name: "", description: "" }

export function AssayGroupsPage() {
  const access = useCurrentUserAccess()
  const allowed = hasPermission(access.data, "assay.panel:view")
  const canCreate = hasPermission(access.data, "assay.panel:edit")
  const client = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [values, setValues] = useState(empty)
  const [idEdited, setIdEdited] = useState(false)
  const [search, setSearch] = useState("")
  const [target, setTarget] = useState<Group | null>(null)
  const [reason, setReason] = useState("")
  const [reasonError, setReasonError] = useState(false)
  const reasonId = useId()
  const impact = useQuery({
    queryKey: ["assay-group-impact", target?.group_id], enabled: Boolean(target), staleTime: 0,
    queryFn: () => api.get<{ group: Group; assays: string[] }>(`/resources/assay-groups/${encodeURIComponent(target!.group_id)}/impact`).then((response) => response.data),
  })
  const status = useMutation({
    mutationFn: () => {
      if (!target || !impact.data || impact.data.group.version !== target.version) throw new Error("Reload the affected assays before confirming")
      return api.patch(`/resources/assay-groups/${encodeURIComponent(target.group_id)}/status`, {
        is_active: !target.is_active, expected_version: target.version, reason: reason.trim(),
      })
    },
    onSuccess: () => {
      setTarget(null)
      for (const key of ["assay-groups", "assay-group-impact", "admin-resource-context", "assay-setup-context", "clinical-rule-authoring-options", "subpanel-all-assays", "admin-public-assay-catalog", "assay-catalog-nav", "public-catalog", "public-catalog-matrix"]) {
        void client.invalidateQueries({ queryKey: [key] })
      }
      notifySuccess("Assay group availability updated")
    },
    onError: (error) => notifyActionError("Update assay group availability", error),
  })
  const groups = useQuery({
    queryKey: ["assay-groups"], enabled: allowed,
    queryFn: () => api.get<{ groups: Group[] }>("/resources/assay-groups").then((response) => response.data.groups),
  })
  const save = useMutation({
    mutationFn: () => api.post("/resources/assay-groups", values),
    onSuccess: () => {
      setCreating(false)
      void client.invalidateQueries({ queryKey: ["assay-groups"] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context"] })
      void client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      notifySuccess("Assay group created")
    },
    onError: (error) => notifyActionError("Create assay group", error),
  })
  const validId = /^[a-z0-9][a-z0-9_-]{0,99}$/.test(values.group_id)
  const rows = (groups.data ?? []).filter((group) => `${group.group_id} ${group.display_name} ${group.description}`.toLowerCase().includes(search.toLowerCase()))
  return <PageShell eyebrow="Admin" title="Assay groups" actions={<AdminHomeLink />}>
    <ConfirmationDialog open={Boolean(target)} title={`${target?.is_active ? "Deactivate" : "Activate"} ${target?.display_name ?? "assay group"}`} confirmLabel={target?.is_active ? "Deactivate group" : "Activate group"} isPending={status.isPending}
      confirmDisabled={impact.isFetching || Boolean(impact.error) || !impact.data || impact.data.group.version !== target?.version}
      onCancel={() => { setTarget(null); if (impact.data && impact.data.group.version !== target?.version) void client.invalidateQueries({ queryKey: ["assay-groups"] }) }} onConfirm={() => { if (!reason.trim()) { setReasonError(true); return } if (impact.data && !impact.error) status.mutate() }}
      description={<div className="space-y-3">
        <p>{target?.is_active ? "New ingest, activation and publication will be blocked for this group. Existing clinical records remain accessible." : "Individually active assays become available again. Inactive child records stay inactive."}</p>
        {impact.error ? <p role="alert" className="text-destructive">Unable to load affected assays. Close and try again.</p> : <div><p className="font-medium">Affected assays ({impact.data?.assays.length ?? 0})</p><ul className="max-h-40 overflow-auto break-words">{impact.data?.assays.map((id) => <li key={id}>{id}</li>)}</ul></div>}
        {impact.isFetching && <p role="status">Loading affected assays...</p>}
        {impact.data && impact.data.group.version !== target?.version && <p role="alert" className="text-destructive">This group has changed. Close and reload the group list before trying again.</p>}
        <div><label className="block" htmlFor={reasonId}>Reason</label><textarea id={reasonId} className="paper-inset mt-1 w-full rounded-md border border-border p-2" maxLength={2000} rows={3} value={reason} aria-invalid={reasonError} onChange={(event) => { setReason(event.target.value); setReasonError(false) }} /></div>
        {reasonError && <p role="alert" className="text-destructive">Enter a reason for this change.</p>}
        {status.error && <p role="alert" className="text-destructive">{status.error.message}</p>}
      </div>} />
    <section aria-label="Assay group registry" className="glass-card min-w-0 space-y-3 p-3">
    {access.isLoading ? <p role="status">Loading access...</p> : !allowed ? <p role="alert">Assay view permission is required.</p> : <>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Input className="max-w-md" aria-label="Search assay groups" placeholder="Search assay groups" value={search} onChange={(event) => setSearch(event.target.value)} />
        {canCreate && !creating && <Button disabled={save.isPending} onClick={() => { setCreating(true); setValues(empty); setIdEdited(false); save.reset() }}><Plus className="h-4 w-4" />Create group</Button>}
      </header>
      {groups.isLoading && <p role="status">Loading assay groups...</p>}
      {groups.error && <p role="alert" className="text-destructive">Unable to load assay groups.</p>}
      {creating && canCreate && <form className="grid gap-4 border-t border-border py-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); if (validId && values.display_name.trim()) save.mutate() }}>
        <h2 className="type-section-title md:col-span-2">New assay group</h2>
        <label className="type-label">Display name<Input required maxLength={200} value={values.display_name} onChange={(event) => {
          const name = event.target.value
          setValues({ ...values, display_name: name, ...(!idEdited ? { group_id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 100) } : {}) })
        }} /></label>
        <label className="type-label">Group identifier<Input required maxLength={100} value={values.group_id} aria-invalid={Boolean(values.group_id) && !validId} aria-describedby="group-id-help" onChange={(event) => { setIdEdited(true); setValues({ ...values, group_id: event.target.value }) }} /><span id="group-id-help" className={values.group_id && !validId ? "text-destructive" : "text-muted-foreground"}>Lowercase letters, numbers, hyphens or underscores. Cannot be renamed after creation.</span></label>
        <label className="type-label md:col-span-2">Description<textarea className="paper-inset mt-1 w-full rounded-md border border-border p-3" maxLength={4000} rows={3} value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} /></label>
        {save.error && <p role="alert" className="text-destructive md:col-span-2">{save.error.message}</p>}
        <div className="flex gap-2 md:col-span-2"><Button type="submit" disabled={save.isPending || !validId || !values.display_name.trim()}><Save className="h-4 w-4" />Save group</Button><Button type="button" variant="outline" disabled={save.isPending} onClick={() => setCreating(false)}><X className="h-4 w-4" />Cancel</Button></div>
      </form>}
      {!groups.isLoading && !groups.error && <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full text-left type-body">
          <thead className="bg-muted"><tr><th className="p-3">Group</th><th className="p-3">Description</th><th className="p-3">Status</th><th className="p-3">Created by / Installed by</th><th className="p-3">Actions</th></tr></thead>
          <tbody>{rows.map((group) => <tr key={group.group_id} className="border-b border-border">
            <td className="max-w-64 break-words p-3"><div className="font-medium">{group.display_name}</div><div className="type-meta text-muted-foreground">{group.group_id}</div></td>
            <td className="max-w-96 whitespace-pre-wrap break-words p-3">{group.description || "-"}</td>
            <td className="p-3"><StatusBadge value={group.is_active} /></td>
            <td className="max-w-64 p-3"><RecordProvenance record={group} /></td>
            <td className="p-3">{canCreate && <button type="button" className="rounded-md p-1.5 text-validation hover:bg-validation/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" title={group.is_active ? "Deactivate group" : "Activate group"} aria-label={`${group.is_active ? "Deactivate" : "Activate"} ${group.display_name}`} disabled={status.isPending} onClick={() => { setTarget(group); setReason(""); setReasonError(false); status.reset() }}><Power className="h-4 w-4" aria-hidden="true" /></button>}</td>
          </tr>)}</tbody>
        </table>{!rows.length && <p className="p-3 text-muted-foreground">No assay groups found.</p>}
      </div>}
    </>}
    </section>
  </PageShell>
}
