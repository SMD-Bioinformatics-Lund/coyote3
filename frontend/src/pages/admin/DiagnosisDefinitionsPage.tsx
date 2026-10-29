import { useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { PageShell } from "@/components/layout/PageShell"
import { DataTable } from "@/components/data-table/DataTable"
import { TableBadge } from "@/components/ui/table-badge"
import { DiagnosisNavigation } from "./DiagnosisNavigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SearchInput } from "@/components/ui/search-input"
import { api } from "@/lib/api"
import { shortResourceName } from "@/lib/resource-names"
import { useDocumentEditor, withDocumentEditor } from "@/hooks/useDocumentEditor"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { DocumentEditorNotice } from "@/components/admin/DocumentEditorNotice"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import type { DiagnosisDefinition } from "./AssayDiagnoses"
import { RecordProvenance } from "./RecordProvenance"
import { AdminHomeLink } from "./AdminHomeLink"
import { BulkInstall } from "@/components/admin/BulkInstall"

type Assay = { asp_id: string; name?: string | null; display_name: string; is_active: boolean }
const empty = { diagnosis_id: "", display_name: "", description: "", is_active: true, asp_ids: [] as string[] }

export function DiagnosisDefinitionsPage() {
  const [params] = useSearchParams()
  const access = useCurrentUserAccess()
  const allowed = hasPermission(access.data, "assay.panel:view") && hasPermission(access.data, "assay.panel:list")
  const canEdit = hasPermission(access.data, "assay.panel:edit")
  const client = useQueryClient()
  const [editing, setEditing] = useState<DiagnosisDefinition | "new" | null>(null)
  const [viewing, setViewing] = useState<DiagnosisDefinition | null>(null)
  const [statusTarget, setStatusTarget] = useState<DiagnosisDefinition | null>(null)
  const viewRef = useRef<HTMLElement>(null)
  useEffect(() => { if (viewing) viewRef.current?.focus() }, [viewing])
  const documentEditor = useDocumentEditor("diagnoses", editing && editing !== "new" ? editing.diagnosis_id : "", canEdit && Boolean(editing && editing !== "new"))
  const [values, setValues] = useState(empty)
  const [idEdited, setIdEdited] = useState(false)
  const [search, setSearch] = useState(params.get("diagnosis") || "")
  const [assaySearch, setAssaySearch] = useState("")
  const definitions = useQuery({
    queryKey: ["diagnosis-definitions"], enabled: allowed,
    queryFn: () => api.get<{ diagnoses: DiagnosisDefinition[] }>("/resources/diagnoses").then((response) => response.data.diagnoses),
  })
  const assays = useQuery({
    queryKey: ["diagnosis-all-assays"], enabled: allowed,
    queryFn: async () => {
      const rows: Assay[] = []
      for (let page = 1; ; page++) {
        const response = await api.get<{ panels: Assay[]; pagination: { total: number } }>(`/resources/asp?page=${page}&per_page=200`)
        rows.push(...response.data.panels)
        if (rows.length >= response.data.pagination.total) return rows
        if (!response.data.panels.length) throw new Error("Assay list changed; reload before selecting assays")
      }
    },
  })
  const refreshDefinitions = () => {
    for (const queryKey of [
      ["diagnosis-definitions"], ["assay-diagnoses"],
      ["admin-resource-context", "aspc"], ["admin-resource-context", "genelists"],
      ["assay-setup-context"], ["clinical-rule-authoring-options"],
    ]) void client.invalidateQueries({ queryKey })
  }
  const statusMutation = useMutation({
    mutationFn: async () => {
      if (!statusTarget || !canEdit || statusTarget.system_installed) throw new Error("Select an editable diagnosis")
      return withDocumentEditor("diagnoses", statusTarget.diagnosis_id, (options) =>
        api.put(`/resources/diagnoses/${encodeURIComponent(statusTarget.diagnosis_id)}`, {
          display_name: statusTarget.display_name, description: statusTarget.description,
          is_active: !statusTarget.is_active, expected_version: statusTarget.version,
          add_asp_ids: [],
        }, options))
    },
    onSuccess: () => {
      setStatusTarget(null)
      setViewing(null)
      refreshDefinitions()
      notifySuccess("Diagnosis availability updated")
    },
    onError: (error) => notifyActionError("Change diagnosis availability", error),
  })
  const mutation = useMutation({
    mutationFn: () => {
      if (editing === "new") return api.post("/resources/diagnoses", values)
      if (!editing) throw new Error("Select a diagnosis")
      return api.put(`/resources/diagnoses/${encodeURIComponent(editing.diagnosis_id)}`, {
        display_name: values.display_name, description: values.description, is_active: values.is_active, expected_version: editing.version,
        add_asp_ids: values.asp_ids,
      }, documentEditor.options())
    },
    onSuccess: () => {
      setEditing(null)
      refreshDefinitions()
      notifySuccess("Shared diagnosis saved")
    },
    onError: (error) => notifyActionError("Save shared diagnosis", error),
  })
  const validId = editing !== "new" || /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(values.diagnosis_id) && values.diagnosis_id !== "base"
  const rows = (definitions.data ?? []).filter((row) => `${row.display_name} ${row.diagnosis_id}`.toLowerCase().includes(search.toLowerCase()))
  return <PageShell eyebrow="Admin" title="Diagnosis definitions" actions={<AdminHomeLink />}>
    <ConfirmationDialog open={Boolean(statusTarget)}
      title={`${statusTarget?.is_active ? "Deactivate" : "Activate"} ${statusTarget?.display_name || "diagnosis"}`}
      confirmLabel={statusTarget?.is_active ? "Deactivate diagnosis" : "Activate diagnosis"}
      isPending={statusMutation.isPending}
      description={<><p>{statusTarget?.is_active ? "This diagnosis will be unavailable for new assignments across all associated assays. Existing samples, annotations and saved reports are preserved." : "This diagnosis will become globally available. Each assay association must also be active for new assignments."}</p>{statusMutation.error && <p role="alert" className="mt-2 text-destructive">{statusMutation.error.message}</p>}</>}
      onCancel={() => setStatusTarget(null)} onConfirm={() => statusMutation.mutate()} />
    <DocumentEditorNotice editor={documentEditor} />
    <section aria-label="Diagnosis registry" className="glass-card min-w-0 space-y-3 p-3">
    <DiagnosisNavigation active="definitions" />
    {allowed && canEdit && <BulkInstall kind="diagnoses" />}
    {access.isLoading ? <p role="status">Loading access...</p> : !allowed ? <p role="alert">Assay list and view permissions are required.</p> : <>
      {definitions.isLoading && <p role="status">Loading diagnoses...</p>}
      {definitions.error && <p role="alert" className="text-destructive">Unable to load shared diagnoses.</p>}
      {!editing && !definitions.isLoading && !definitions.error && <DataTable
        data={rows}
        stateKey="diagnosis-definitions"
        rowLabel="diagnoses"
        hideExport
        emptyMessage="No diagnoses found."
        searchPlaceholder="Search diagnosis definitions"
        searchValue={search}
        onSearchChange={setSearch}
        renderToolbar={() => canEdit && <Button disabled={mutation.isPending} onClick={() => { setEditing("new"); setValues(empty); setIdEdited(false); setAssaySearch(""); mutation.reset() }}><icon.plus className="h-4 w-4" />Create diagnosis</Button>}
        columns={[
          { accessorKey: "display_name", header: "Diagnosis", cell: ({ row }) => <div className="max-w-64 break-words"><div className="font-semibold">{row.original.display_name}</div><span className="type-meta text-muted-foreground">{row.original.diagnosis_id}</span></div> },
          { accessorKey: "description", header: "Description", cell: ({ row }) => <span className="block max-w-96 whitespace-pre-wrap break-words">{row.original.description || "-"}</span> },
          { id: "assays", header: "Associated assays", cell: ({ row }) => <div className="flex max-w-80 flex-wrap gap-2">{row.original.associated_asp_ids?.length ? row.original.associated_asp_ids.map((id) => {
            const assay = assays.data?.find(item => item.asp_id === id)
            return <Link key={id} className="inline-flex hover:underline" to={`/admin/assay-diagnoses?assay=${encodeURIComponent(id)}`}>
              <TableBadge className="badge-tone-blue" title={`${assay?.display_name || id} · ${id}`}>
                {shortResourceName(assay, id)}
              </TableBadge>
            </Link>
          }) : "None"}</div> },
          { accessorKey: "is_active", header: "Global status", cell: ({ row }) => <TableBadge className={row.original.is_active ? "border-pass/40 bg-pass/10 text-pass" : "border-muted-foreground/30 bg-muted text-muted-foreground"}>{row.original.is_active ? "Available" : "Retired"}</TableBadge> },
          { id: "record_provenance", header: "Created by", cell: ({ row }) => <RecordProvenance record={row.original} /> },
          { accessorKey: "updated_by", header: "Updated by", cell: ({ row }) => <RecordProvenance record={row.original} kind="updated" /> },
          { id: "actions", header: "Actions", enableSorting: false, cell: ({ row: { original: row } }) => <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" title={`View ${row.display_name}`} aria-label={`View ${row.display_name}`} onClick={() => setViewing(row)}><icon.eye className="h-4 w-4" /></Button>
            {canEdit && !row.system_installed && <>
              <Button variant="ghost" size="icon" title={`Edit ${row.display_name}`} aria-label={`Edit ${row.display_name}`} disabled={mutation.isPending || statusMutation.isPending} onClick={() => { setViewing(null); setEditing(row); setValues({ ...empty, ...row, asp_ids: [] }); setAssaySearch(""); mutation.reset() }}><icon.edit className="h-4 w-4" /></Button>
              <Button variant="ghost" size="icon" className="text-validation" title={`${row.is_active ? "Deactivate" : "Activate"} ${row.display_name}`} aria-label={`${row.is_active ? "Deactivate" : "Activate"} ${row.display_name}`} disabled={mutation.isPending || statusMutation.isPending} onClick={() => { setStatusTarget(row); statusMutation.reset() }}><icon.power className="h-4 w-4" /></Button>
            </>}
          </div> },
        ]}
      />}
      {viewing && !editing && <section ref={viewRef} tabIndex={-1} aria-label="Diagnosis details" className="paper-inset space-y-3 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between gap-3"><h2 className="type-section-title">{viewing.display_name}</h2><Button variant="ghost" size="icon" aria-label="Close diagnosis details" onClick={() => setViewing(null)}><icon.x className="h-4 w-4" /></Button></div>
        <p className="type-body text-muted-foreground">{viewing.system_installed ? "System-installed definition. Editing and availability changes are managed by the application installation." : !canEdit ? "Read-only access. Assay edit permission is required to change this definition." : "Shared definition. Availability changes apply across all associated assays."}</p>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div><dt className="type-label text-muted-foreground">Identifier</dt><dd className="break-words type-body">{viewing.diagnosis_id}</dd></div>
          <div><dt className="type-label text-muted-foreground">Global status</dt><dd><TableBadge className={viewing.is_active ? "border-pass/40 bg-pass/10 text-pass" : "border-muted-foreground/30 bg-muted text-muted-foreground"}>{viewing.is_active ? "Available" : "Retired"}</TableBadge></dd></div>
          <div className="sm:col-span-2"><dt className="type-label text-muted-foreground">Description</dt><dd className="whitespace-pre-wrap break-words type-body">{viewing.description || "No description provided."}</dd></div>
          <div><dt className="type-label text-muted-foreground">Version</dt><dd className="type-body">{viewing.version}</dd></div>
          <div><dt className="type-label text-muted-foreground">Associated assays</dt><dd className="flex flex-wrap gap-2">{viewing.associated_asp_ids?.length ? viewing.associated_asp_ids.map(id => <Link key={id} className="break-all text-primary underline" to={`/admin/assay-diagnoses?assay=${encodeURIComponent(id)}`}>{shortResourceName(assays.data?.find(assay => assay.asp_id === id), id)}</Link>) : "None"}</dd></div>
          <div><dt className="type-label text-muted-foreground">Created by</dt><dd><RecordProvenance record={viewing} /></dd></div>
          <div><dt className="type-label text-muted-foreground">Updated by</dt><dd><RecordProvenance record={viewing} kind="updated" /></dd></div>
        </dl>
      </section>}
      {canEdit && editing && <form onSubmit={(event) => { event.preventDefault(); if (documentEditor.owned && validId && values.display_name.trim()) mutation.mutate() }}><fieldset disabled={!documentEditor.owned} className="grid gap-4 border-t border-border py-4 md:grid-cols-2">
        <h2 className="text-lg font-semibold md:col-span-2">{editing === "new" ? "New diagnosis" : "Edit shared definition"}</h2>
        {editing !== "new" && <p className="type-body md:col-span-2" role="status">Changes apply to every associated assay.</p>}
        <div><label className="type-label">Display name<Input autoFocus required maxLength={200} value={values.display_name} onChange={(event) => {
          const name = event.target.value
          setValues({ ...values, display_name: name, ...(editing === "new" && !idEdited ? { diagnosis_id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 100).replace(/^-|-$/g, "") } : {}) })
        }} /></label>
        <p className="mt-1 type-meta text-muted-foreground">Display name is the readable diagnosis label used in cards, tables and dropdowns. Diagnoses have no separate short-name field; the identifier remains the stable reference.</p></div>
        <label className="type-label">Diagnosis identifier<Input required readOnly={editing !== "new"} maxLength={100} value={values.diagnosis_id} aria-invalid={Boolean(values.diagnosis_id) && !validId} onChange={(event) => { setIdEdited(true); setValues({ ...values, diagnosis_id: event.target.value }) }} />
          {values.diagnosis_id && !validId && <span className="text-destructive">Use lowercase letters, numbers, hyphens between distinct terms; underscores within names. Base is implicit.</span>}
        </label>
        <label className="type-label md:col-span-2">Description<textarea className="paper-inset mt-1 w-full rounded-md border border-border p-3" rows={3} maxLength={4000} value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} /></label>
        <label className="flex items-center gap-2 type-body"><input type="checkbox" checked={values.is_active} onChange={(event) => setValues({ ...values, is_active: event.target.checked })} />Globally available</label>
        <fieldset className="min-w-0 space-y-3 border-t border-border pt-3 md:col-span-2"><legend className="type-label">Associate assays</legend>
          {editing !== "new" && <p className="type-meta text-muted-foreground">Existing associations: {editing.associated_asp_ids?.join(", ") || "None"}. Deactivate existing links on the Assay associations tab.</p>}
          <SearchInput aria-label="Search available assays" placeholder="Search assays" value={assaySearch} onChange={(event) => setAssaySearch(event.target.value)} />
          <p className="type-meta text-muted-foreground">{values.asp_ids.length} selected</p>
          {assays.isLoading && <p role="status">Loading assays...</p>}
          {assays.error && <p role="alert" className="text-destructive">Unable to load available assays.</p>}
          <div className="grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">{(assays.data ?? []).filter((assay) => assay.is_active && `${assay.name || ""} ${assay.display_name} ${assay.asp_id}`.toLowerCase().includes(assaySearch.toLowerCase())).map((assay) => {
            const linked = editing !== "new" && Boolean(editing.associated_asp_ids?.includes(assay.asp_id))
            return <label key={assay.asp_id} className="form-option flex min-w-0 items-start gap-2 p-2 type-body" title={assay.display_name}><input type="checkbox" disabled={linked} checked={linked || values.asp_ids.includes(assay.asp_id)} onChange={(event) => setValues({ ...values, asp_ids: event.target.checked ? [...values.asp_ids, assay.asp_id] : values.asp_ids.filter((id) => id !== assay.asp_id) })} /><span className="min-w-0 break-words">{shortResourceName(assay, assay.asp_id)}<span className="block type-meta text-muted-foreground">{assay.asp_id}{linked ? " (Associated)" : ""}</span></span></label>
          })}</div>
        </fieldset>
        {mutation.error && <p role="alert" className="text-destructive md:col-span-2">{mutation.error.message}</p>}
        <div className="flex gap-2 md:col-span-2"><Button type="submit" disabled={mutation.isPending || !validId || !values.display_name.trim() || editing === "new" && (assays.isLoading || Boolean(assays.error))}><icon.save className="h-4 w-4" />Save diagnosis</Button><Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => setEditing(null)}><icon.x className="h-4 w-4" />Cancel</Button></div>
      </fieldset></form>}
    </>}
    </section>
  </PageShell>
}
