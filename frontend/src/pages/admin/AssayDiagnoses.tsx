import { useState } from "react"
import { Link } from "react-router-dom"
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

export type DiagnosisDefinition = RecordProvenanceData & {
  diagnosis_id: string
  display_name: string
  description: string
  is_active: boolean
  version: number
  associated_asp_ids?: string[]
}
type Association = DiagnosisDefinition & { definition_is_active: boolean }

export function AssayDiagnoses({ aspId, canEdit }: { aspId: string; canEdit: boolean }) {
  const client = useQueryClient()
  const endpoint = `/resources/asp/${encodeURIComponent(aspId)}/diagnoses`
  const [search, setSearch] = useState("")
  const associations = useQuery({
    queryKey: ["assay-diagnoses", aspId],
    queryFn: () => api.get<{ diagnoses: Association[] }>(endpoint).then((response) => response.data.diagnoses),
  })
  const mutation = useMutation({
    mutationFn: (association: Association) => api.patch(`${endpoint}/${encodeURIComponent(association.diagnosis_id)}/status`, { is_active: !association.is_active, expected_version: association.version }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["assay-diagnoses", aspId] })
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
  const rows = (associations.data ?? []).filter((row) => `${row.diagnosis_id} ${row.display_name}`.toLowerCase().includes(search.toLowerCase()))
  return <section className="min-w-0 space-y-3" aria-label="Assay diagnosis associations">
    {loading && <p role="status">Loading associations...</p>}
    {error && <p role="alert" className="text-destructive">Unable to load diagnosis associations.</p>}
    {mutation.error && <p role="alert" className="text-destructive">{mutation.error.message}</p>}
    {!loading && !error && <DataTable
      data={rows}
      stateKey={`assay-diagnoses-${aspId}`}
      rowLabel="associated diagnoses"
      hideExport
      emptyMessage={search ? "No associated diagnoses match your search." : "No diagnoses are associated with this assay."}
      searchPlaceholder="Search diagnoses"
      searchValue={search}
      onSearchChange={setSearch}
      columns={[
        { accessorKey: "display_name", header: "Diagnosis", cell: ({ row }) => <div className="max-w-80 break-words"><Link className="font-semibold text-primary underline-offset-4 hover:underline" to={`/admin/diagnoses?diagnosis=${encodeURIComponent(row.original.diagnosis_id)}`}>{row.original.display_name}</Link><div className="type-meta text-muted-foreground">{row.original.diagnosis_id}</div></div> },
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
