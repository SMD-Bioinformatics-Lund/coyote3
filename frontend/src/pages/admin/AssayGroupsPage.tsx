import { useId, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Power, Save, X } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { DataTable } from "@/components/data-table/DataTable"
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

type Group = RecordProvenanceData & { group_id: string; parent_group_id: string | null; display_name: string; description: string; system_managed: boolean; is_active: boolean; version: number }
const empty = { group_id: "", parent_group_id: "", display_name: "", description: "" }

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
      for (const key of ["assay-groups", "assay-group-impact", "admin-resource-context", "assay-setup-context", "clinical-rule-authoring-options", "diagnosis-all-assays", "admin-public-assay-catalog", "assay-catalog-nav", "public-catalog", "public-catalog-matrix"]) {
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
    mutationFn: () => api.post("/resources/assay-groups", { ...values, parent_group_id: values.parent_group_id || null }),
    onSuccess: () => {
      setCreating(false)
      void client.invalidateQueries({ queryKey: ["assay-groups"] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context"] })
      void client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      notifySuccess("Assay group created")
    },
    onError: (error) => notifyActionError("Create assay group", error),
  })
  const validId = /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(values.group_id)
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
      {groups.isLoading && <p role="status">Loading assay groups...</p>}
      {groups.error && <p role="alert" className="text-destructive">Unable to load assay groups.</p>}
      {creating && canCreate && <form className="grid gap-4 border-t border-border py-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); if (validId && values.display_name.trim()) save.mutate() }}>
        <h2 className="type-section-title md:col-span-2">New assay group</h2>
        <label className="type-label">Display name<Input required maxLength={200} value={values.display_name} onChange={(event) => {
          const name = event.target.value
          setValues({ ...values, display_name: name, ...(!idEdited ? { group_id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 100).replace(/^-|-$/g, "") } : {}) })
        }} /></label>
        <label className="type-label">Group identifier<Input required maxLength={100} value={values.group_id} aria-invalid={Boolean(values.group_id) && !validId} aria-describedby="group-id-help" onChange={(event) => { setIdEdited(true); setValues({ ...values, group_id: event.target.value }) }} /><span id="group-id-help" className={values.group_id && !validId ? "text-destructive" : "text-muted-foreground"}>Lowercase letters, numbers, hyphens between distinct terms; underscores within names. Cannot be renamed after creation.</span></label>
        <label className="type-label md:col-span-2">Description<textarea className="paper-inset mt-1 w-full rounded-md border border-border p-3" maxLength={4000} rows={3} value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} /></label>
        <label className="type-label">Parent group (optional)
          <select className="paper-inset mt-1 w-full rounded-md border border-border p-2" value={values.parent_group_id} onChange={(event) => setValues({ ...values, parent_group_id: event.target.value })}>
            <option value="">None — top-level group</option>
            {(groups.data ?? []).filter((group) => group.is_active).map((group) => <option key={group.group_id} value={group.group_id}>{group.display_name} ({group.group_id})</option>)}
          </select>
          <span className="type-meta text-muted-foreground">Parent classifications provide fallback evidence and require confirmation for this assay and diagnosis. Access and assay assignments remain explicit.</span>
        </label>
        {save.error && <p role="alert" className="text-destructive md:col-span-2">{save.error.message}</p>}
        <div className="flex gap-2 md:col-span-2"><Button type="submit" disabled={save.isPending || !validId || !values.display_name.trim()}><Save className="h-4 w-4" />Save group</Button><Button type="button" variant="outline" disabled={save.isPending} onClick={() => setCreating(false)}><X className="h-4 w-4" />Cancel</Button></div>
      </form>}
      {!groups.isLoading && !groups.error && <DataTable
        data={rows}
        stateKey="assay-groups"
        rowLabel="groups"
        hideExport
        emptyMessage="No assay groups found."
        searchPlaceholder="Search assay groups"
        searchValue={search}
        onSearchChange={setSearch}
        renderToolbar={() => canCreate && !creating && <Button disabled={save.isPending} onClick={() => { setCreating(true); setValues(empty); setIdEdited(false); save.reset() }}><Plus className="h-4 w-4" />Create group</Button>}
        columns={[
          { accessorKey: "display_name", header: "Group", cell: ({ row }) => <div className="max-w-64 break-words"><div className="font-semibold">{row.original.display_name}</div><div className="type-meta text-muted-foreground">{row.original.group_id}</div></div> },
          { accessorKey: "description", header: "Description", cell: ({ row }) => <span className="block max-w-96 whitespace-pre-wrap break-words">{row.original.description || "-"}</span> },
          { accessorKey: "parent_group_id", header: "Biological parent", cell: ({ row }) => row.original.parent_group_id ? (groups.data ?? []).find((group) => group.group_id === row.original.parent_group_id)?.display_name ?? row.original.parent_group_id : "Top-level group" },
          { accessorKey: "is_active", header: "Status", cell: ({ row }) => <StatusBadge value={row.original.is_active} /> },
          { id: "record_provenance", header: "Created by", enableSorting: false, cell: ({ row }) => <RecordProvenance record={row.original} /> },
          { accessorKey: "updated_by", header: "Updated by" },
          { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => {
            const group = row.original
            return canCreate && !group.system_managed && !group.system_installed && <Button variant="ghost" size="icon" className="text-validation" title={group.is_active ? "Deactivate group" : "Activate group"} aria-label={`${group.is_active ? "Deactivate" : "Activate"} ${group.display_name}`} disabled={status.isPending} onClick={() => { setTarget(group); setReason(""); setReasonError(false); status.reset() }}><Power className="h-4 w-4" aria-hidden="true" /></Button>
          } },
        ]}
      />}
    </>}
    </section>
  </PageShell>
}
