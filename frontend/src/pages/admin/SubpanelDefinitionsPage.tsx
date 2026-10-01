import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Edit, Plus, Save, X } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { SubpanelNavigation } from "./SubpanelNavigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import type { SubpanelDefinition } from "./AssaySubpanels"
import { RecordProvenance } from "./RecordProvenance"
import { AdminHomeLink } from "./AdminHomeLink"

type Assay = { asp_id: string; display_name: string; is_active: boolean }
const empty = { subpanel_id: "", display_name: "", description: "", is_active: true, asp_ids: [] as string[] }

export function SubpanelDefinitionsPage() {
  const access = useCurrentUserAccess()
  const allowed = hasPermission(access.data, "assay.panel:view") && hasPermission(access.data, "assay.panel:list")
  const canEdit = hasPermission(access.data, "assay.panel:edit")
  const client = useQueryClient()
  const [editing, setEditing] = useState<SubpanelDefinition | "new" | null>(null)
  const [values, setValues] = useState(empty)
  const [idEdited, setIdEdited] = useState(false)
  const [search, setSearch] = useState("")
  const [assaySearch, setAssaySearch] = useState("")
  const definitions = useQuery({
    queryKey: ["subpanel-definitions"], enabled: allowed,
    queryFn: () => api.get<{ subpanels: SubpanelDefinition[] }>("/resources/subpanels").then((response) => response.data.subpanels),
  })
  const assays = useQuery({
    queryKey: ["subpanel-all-assays"], enabled: allowed && canEdit && Boolean(editing),
    queryFn: async () => {
      const rows: Assay[] = []
      for (let page = 1; ; page++) {
        const response = await api.get<{ panels: Assay[]; pagination: { total: number } }>(`/resources/asp?page=${page}&per_page=200`)
        rows.push(...response.data.panels)
        if (rows.length >= response.data.pagination.total) return rows.filter((row) => row.is_active)
        if (!response.data.panels.length) throw new Error("Assay list changed; reload before selecting assays")
      }
    },
  })
  const mutation = useMutation({
    mutationFn: () => {
      if (editing === "new") return api.post("/resources/subpanels", values)
      if (!editing) throw new Error("Select a subpanel")
      return api.put(`/resources/subpanels/${encodeURIComponent(editing.subpanel_id)}`, {
        display_name: values.display_name, description: values.description, is_active: values.is_active, expected_version: editing.version,
        add_asp_ids: values.asp_ids,
      })
    },
    onSuccess: () => {
      setEditing(null)
      void client.invalidateQueries({ queryKey: ["subpanel-definitions"] })
      void client.invalidateQueries({ queryKey: ["assay-subpanels"] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context", "aspc"] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context", "genelists"] })
      void client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      notifySuccess("Shared subpanel saved")
    },
    onError: (error) => notifyActionError("Save shared subpanel", error),
  })
  const validId = editing !== "new" || /^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(values.subpanel_id) && values.subpanel_id !== "base"
  const rows = (definitions.data ?? []).filter((row) => `${row.display_name} ${row.subpanel_id}`.toLowerCase().includes(search.toLowerCase()))
  return <PageShell eyebrow="Admin" title="Subpanel definitions" actions={<AdminHomeLink />}>
    <section aria-label="Subpanel registry" className="glass-card min-w-0 space-y-3 p-3">
    <SubpanelNavigation active="definitions" />
    {access.isLoading ? <p role="status">Loading access...</p> : !allowed ? <p role="alert">Assay list and view permissions are required.</p> : <>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Input className="sm:max-w-md" aria-label="Search subpanel definitions" placeholder="Search subpanels" value={search} onChange={(event) => setSearch(event.target.value)} />
        {canEdit && !editing && <Button disabled={mutation.isPending} onClick={() => { setEditing("new"); setValues(empty); setIdEdited(false); setAssaySearch(""); mutation.reset() }}><Plus className="h-4 w-4" />Create subpanel</Button>}
      </header>
      {definitions.isLoading && <p role="status">Loading subpanels...</p>}
      {definitions.error && <p role="alert" className="text-destructive">Unable to load shared subpanels.</p>}
      {!editing && !definitions.isLoading && !definitions.error && <div className="overflow-x-auto rounded-lg border border-border bg-card"><table className="w-full text-left text-sm">
        <thead className="bg-muted"><tr><th className="p-3">Subpanel</th><th className="p-3">Description</th><th className="p-3">Global status</th><th className="p-3">Installed by</th><th className="p-3">Actions</th></tr></thead>
        <tbody>{rows.map((row) => <tr className="border-b border-border" key={row.subpanel_id}>
          <td className="max-w-64 break-words p-3"><div className="font-medium">{row.display_name}</div><span className="type-meta text-muted-foreground">{row.subpanel_id}</span></td>
          <td className="max-w-96 whitespace-pre-wrap break-words p-3">{row.description || "-"}</td>
          <td className="p-3">{row.is_active ? "Available" : "Retired"}</td>
          <td className="max-w-64 p-3"><RecordProvenance record={row} /></td>
          <td className="p-3">{canEdit && <Button variant="outline" size="icon" title={`Edit ${row.display_name}`} aria-label={`Edit ${row.display_name}`} disabled={mutation.isPending} onClick={() => { setEditing(row); setValues({ ...empty, ...row, asp_ids: [] }); setAssaySearch(""); mutation.reset() }}><Edit className="h-4 w-4" /></Button>}</td>
        </tr>)}</tbody>
      </table>{!rows.length && <p className="p-3 text-muted-foreground">No subpanels found.</p>}</div>}
      {canEdit && editing && <form className="grid gap-4 border-t border-border py-4 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); if (validId && values.display_name.trim()) mutation.mutate() }}>
        <h2 className="text-lg font-semibold md:col-span-2">{editing === "new" ? "New subpanel" : "Edit shared definition"}</h2>
        {editing !== "new" && <p className="type-body md:col-span-2" role="status">Changes apply to every associated assay.</p>}
        <label className="type-label">Display name<Input autoFocus required maxLength={200} value={values.display_name} onChange={(event) => {
          const name = event.target.value
          setValues({ ...values, display_name: name, ...(editing === "new" && !idEdited ? { subpanel_id: name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 100).replace(/^_|_$/g, "") } : {}) })
        }} /></label>
        <label className="type-label">Subpanel identifier<Input required readOnly={editing !== "new"} maxLength={100} value={values.subpanel_id} aria-invalid={Boolean(values.subpanel_id) && !validId} onChange={(event) => { setIdEdited(true); setValues({ ...values, subpanel_id: event.target.value }) }} />
          {values.subpanel_id && !validId && <span className="text-destructive">Use lowercase letters, numbers, single underscores between words. Base is implicit.</span>}
        </label>
        <label className="type-label md:col-span-2">Description<textarea className="paper-inset mt-1 w-full rounded-md border border-border p-3" rows={3} maxLength={4000} value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} /></label>
        <label className="flex items-center gap-2 type-body"><input type="checkbox" checked={values.is_active} onChange={(event) => setValues({ ...values, is_active: event.target.checked })} />Globally available</label>
        <fieldset className="min-w-0 space-y-3 border-t border-border pt-3 md:col-span-2"><legend className="type-label">Associate assays</legend>
          {editing !== "new" && <p className="type-meta text-muted-foreground">Existing associations: {editing.associated_asp_ids?.join(", ") || "None"}. Deactivate existing links on the Assay associations tab.</p>}
          <Input aria-label="Search available assays" placeholder="Search assays" value={assaySearch} onChange={(event) => setAssaySearch(event.target.value)} />
          <p className="type-meta text-muted-foreground">{values.asp_ids.length} selected</p>
          {assays.isLoading && <p role="status">Loading assays...</p>}
          {assays.error && <p role="alert" className="text-destructive">Unable to load available assays.</p>}
          <div className="grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">{(assays.data ?? []).filter((assay) => `${assay.display_name} ${assay.asp_id}`.toLowerCase().includes(assaySearch.toLowerCase())).map((assay) => {
            const linked = editing !== "new" && Boolean(editing.associated_asp_ids?.includes(assay.asp_id))
            return <label key={assay.asp_id} className="flex min-w-0 items-start gap-2 p-2 type-body"><input type="checkbox" disabled={linked} checked={linked || values.asp_ids.includes(assay.asp_id)} onChange={(event) => setValues({ ...values, asp_ids: event.target.checked ? [...values.asp_ids, assay.asp_id] : values.asp_ids.filter((id) => id !== assay.asp_id) })} /><span className="min-w-0 break-words">{assay.display_name || assay.asp_id}<span className="block type-meta text-muted-foreground">{assay.asp_id}{linked ? " (Associated)" : ""}</span></span></label>
          })}</div>
        </fieldset>
        {mutation.error && <p role="alert" className="text-destructive md:col-span-2">{mutation.error.message}</p>}
        <div className="flex gap-2 md:col-span-2"><Button type="submit" disabled={mutation.isPending || !validId || !values.display_name.trim() || editing === "new" && (assays.isLoading || Boolean(assays.error))}><Save className="h-4 w-4" />Save subpanel</Button><Button type="button" variant="outline" disabled={mutation.isPending} onClick={() => setEditing(null)}><X className="h-4 w-4" />Cancel</Button></div>
      </form>}
    </>}
    </section>
  </PageShell>
}
