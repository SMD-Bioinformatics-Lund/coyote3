import { useState } from "react"
import { Power } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RecordProvenance } from "./RecordProvenance"
import type { RecordProvenanceData } from "./record-provenance"
import { StatusBadge } from "./resource-list"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

export type SubpanelDefinition = RecordProvenanceData & {
  subpanel_id: string
  display_name: string
  description: string
  is_active: boolean
  version: number
  associated_asp_ids?: string[]
}
type Association = SubpanelDefinition & { definition_is_active: boolean }

export function AssaySubpanels({ aspId, canEdit }: { aspId: string; canEdit: boolean }) {
  const client = useQueryClient()
  const endpoint = `/resources/asp/${encodeURIComponent(aspId)}/subpanels`
  const [search, setSearch] = useState("")
  const associations = useQuery({
    queryKey: ["assay-subpanels", aspId],
    queryFn: () => api.get<{ subpanels: Association[] }>(endpoint).then((response) => response.data.subpanels),
  })
  const mutation = useMutation({
    mutationFn: (association: Association) => api.patch(`${endpoint}/${encodeURIComponent(association.subpanel_id)}/status`, { is_active: !association.is_active, expected_version: association.version }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["assay-subpanels", aspId] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context", "aspc"] })
      void client.invalidateQueries({ queryKey: ["admin-resource-context", "genelists"] })
      void client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      notifySuccess("Assay association updated")
    },
    onError: (error) => notifyActionError("Update assay association", error),
  })
  const loading = associations.isLoading
  const error = associations.error
  const rows = (associations.data ?? []).filter((row) => `${row.subpanel_id} ${row.display_name}`.toLowerCase().includes(search.toLowerCase()))
  return <section className="min-w-0 space-y-3" aria-label="Assay subpanel associations">
    <div className="flex flex-wrap items-center justify-between gap-3"><Input className="sm:max-w-md" aria-label="Search subpanels" placeholder="Search subpanels" value={search} onChange={(event) => setSearch(event.target.value)} /><span className="type-meta text-muted-foreground">{rows.length} associated subpanels</span></div>
    {loading && <p role="status">Loading associations...</p>}
    {error && <p role="alert" className="text-destructive">Unable to load subpanel associations.</p>}
    {mutation.error && <p role="alert" className="text-destructive">{mutation.error.message}</p>}
    {!loading && !error && <div className="overflow-x-auto rounded-lg border border-border bg-card"><table className="w-full text-left text-sm">
      <thead className="bg-muted"><tr><th className="p-3">Subpanel</th><th className="p-3">Shared status</th><th className="p-3">Assay status</th><th className="p-3">Created by / Installed by</th><th className="p-3">Actions</th></tr></thead>
      <tbody>{rows.map((association) => {
        const active = association.is_active
        return <tr key={association.subpanel_id} className="border-b border-border">
          <td className="max-w-80 break-words p-3"><div className="font-medium">{association.display_name}</div><span className="type-meta text-muted-foreground">{association.subpanel_id}</span></td>
          <td className="p-3">{association.definition_is_active ? "Available" : "Globally retired"}</td>
          <td className="p-3"><StatusBadge value={active} /></td>
          <td className="max-w-64 p-3"><RecordProvenance record={association} /></td>
          <td className="p-3">
            <button type="button" className="rounded-md p-1.5 text-validation hover:bg-validation/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50" title={active ? "Deactivate association" : "Activate association"} aria-label={`${active ? "Deactivate" : "Activate"} ${association.display_name} for ${aspId}`} disabled={!canEdit || mutation.isPending || (!association.definition_is_active && !active)} onClick={() => mutation.mutate(association)}>
              <Power className="h-4 w-4" aria-hidden="true" />
            </button>
          </td>
        </tr>
      })}</tbody>
    </table>{!rows.length && <p className="p-3 text-muted-foreground">{search ? "No associated subpanels match your search." : "No subpanels are associated with this assay."}</p>}</div>}
  </section>
}
