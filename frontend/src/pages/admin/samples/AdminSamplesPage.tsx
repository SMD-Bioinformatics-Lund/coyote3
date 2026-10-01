import { AdminActionDialog, AdminListContent, AdminListToolbar, AdminRowActions } from "@/components/admin/AdminListControls"
import { useAdminList } from "@/components/admin/useAdminList"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import type { ColumnDef } from "@tanstack/react-table"
import { Plus } from "lucide-react"
import { Link } from "react-router-dom"
import { adminCell, adminExportValue, adminFields, titleize } from "../resource-list"
import { filters, columns as preferredColumns, resource as spec } from "./resource"

const invalidateKeys = [["samples"], ["sample-navigation-counts"]]

export function AdminSamplesPage() {
  const state = useAdminList({ spec, filters, serverFilters: true, sampleNotifications: true, invalidateKeys })
  const { data, rows, visibleRows, canCreate } = state
  const fields = adminFields(preferredColumns, rows)
  const tableColumns: ColumnDef<Record<string, unknown>>[] = [
    ...fields.map((field): ColumnDef<Record<string, unknown>> => ({
      id: field,
      header: titleize(field),
      accessorFn: (row) => adminExportValue(field, row),
      cell: ({ row }) => adminCell(field, row.original, {
        roleColors: data?.roles || {},
        primaryIdentifier: field === spec.idKeys[0],
      }),
      meta: {
        exportValue: (row: Record<string, unknown>) => adminExportValue(field, row),
        cellClassName: field === "permissions" ? "min-w-64" : undefined,
      },
    })),
    { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <AdminRowActions state={state} spec={spec} row={row.original} /> },
  ]
  return (
    <PageShell eyebrow="Admin" title={spec.title} description={spec.description} actions={<>
      {canCreate && <Link to="/admin/samples/create" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"><Plus className="h-4 w-4" />Create</Link>}
      <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">Admin home</Link>
    </>}>
      <div className="glass-card p-3">
        <AdminListToolbar state={state} spec={spec} />
        <AdminListContent state={state} spec={spec}>
          <DataTable columns={tableColumns} data={visibleRows} filename="samples.csv" hideSearch />
        </AdminListContent>
      </div>

      <AdminActionDialog state={state} spec={spec} />
    </PageShell>
  )
}
