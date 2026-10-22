import { useState } from "react"
import { Power } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RecordProvenance } from "./RecordProvenance"
import type { RecordProvenanceData } from "./record-provenance"
import { StatusBadge } from "./resource-list"
import { DataTable } from "@/components/data-table/DataTable"
import { TableBadge } from "@/components/ui/table-badge"
import { Button } from "@/components/ui/button"
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
    {loading && <p role="status">Loading associations...</p>}
    {error && <p role="alert" className="text-destructive">Unable to load subpanel associations.</p>}
    {mutation.error && <p role="alert" className="text-destructive">{mutation.error.message}</p>}
    {!loading && !error && <DataTable
      data={rows}
      stateKey={`assay-subpanels-${aspId}`}
      rowLabel="associated subpanels"
      hideExport
      emptyMessage={search ? "No associated subpanels match your search." : "No subpanels are associated with this assay."}
      searchPlaceholder="Search subpanels"
      searchValue={search}
      onSearchChange={setSearch}
      columns={[
        { accessorKey: "display_name", header: "Subpanel", cell: ({ row }) => <div className="max-w-80 break-words"><div className="font-semibold">{row.original.display_name}</div><span className="type-meta text-muted-foreground">{row.original.subpanel_id}</span></div> },
        { accessorKey: "definition_is_active", header: "Shared status", cell: ({ row }) => <TableBadge className={row.original.definition_is_active ? "border-pass/40 bg-pass/10 text-pass" : "border-muted-foreground/30 bg-muted text-muted-foreground"}>{row.original.definition_is_active ? "Available" : "Globally retired"}</TableBadge> },
        { accessorKey: "is_active", header: "Assay status", cell: ({ row }) => <StatusBadge value={row.original.is_active} /> },
        { id: "record_provenance", header: "Installed by", enableSorting: false, cell: ({ row }) => <RecordProvenance record={row.original} /> },
        { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => {
          const association = row.original
          const active = association.is_active
          return <Button variant="ghost" size="icon" className="text-validation" title={active ? "Deactivate association" : "Activate association"} aria-label={`${active ? "Deactivate" : "Activate"} ${association.display_name} for ${aspId}`} disabled={!canEdit || mutation.isPending || (!association.definition_is_active && !active)} onClick={() => mutation.mutate(association)}><Power className="h-4 w-4" aria-hidden="true" /></Button>
        } },
      ]}
    />}
  </section>
}
