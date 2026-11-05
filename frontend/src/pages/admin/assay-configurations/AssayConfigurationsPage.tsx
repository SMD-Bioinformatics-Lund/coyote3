import { AdminActionDialog, AdminListContent, AdminListToolbar, AdminRowActions } from "@/components/admin/AdminListControls"
import { useAdminList } from "@/components/admin/useAdminList"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import type { ColumnDef } from "@tanstack/react-table"
import { icon } from "@/lib/assets"
import { Link, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { hasPermission } from "@/lib/access-control"
import { api } from "@/lib/api"
import { notifyActionError } from "@/lib/notifications"
import { CopySetupConfiguration } from "./CopySetupConfiguration"
import { adminCell, adminColumnTitle, adminExportValue, adminFields } from "../resource-list"
import { filters, columns as preferredColumns, resource as spec } from "./resource"

export function AssayConfigurationsPage() {
  const state = useAdminList({ spec, filters })
  const { data, rows, visibleRows, canCreate } = state
  const navigate = useNavigate()
  const [showDrafts, setShowDrafts] = useState(false)
  const canReadDrafts = canCreate && hasPermission(state.accessQuery.data, "assay.panel:list") && hasPermission(state.accessQuery.data, "assay.panel:view")
  const copy = useMutation({
    mutationFn: (identifier: string) => api.get<{ assay_config: Record<string, unknown> }>(`${spec.endpoint}/${encodeURIComponent(identifier)}/context`).then(result => result.data.assay_config),
    onSuccess: copiedDocument => navigate("/admin/aspc/create", { state: { copiedDocument } }),
    onError: error => notifyActionError("Could not copy configuration", error),
  })
  const fields = adminFields(preferredColumns, rows)
  const tableColumns: ColumnDef<Record<string, unknown>>[] = [
    ...fields.map((field): ColumnDef<Record<string, unknown>> => ({
      id: field,
      header: adminColumnTitle(field),
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
    { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <div className="flex flex-wrap items-center gap-2"><AdminRowActions state={state} spec={spec} row={row.original} />{canCreate && state.canView && <Button variant="outline" size="sm" disabled={copy.isPending} onClick={() => copy.mutate(String(row.original.aspc_id))} aria-label={`Copy ${String(row.original.aspc_id)} as new`}>Copy as new</Button>}</div> },
  ]
  return (
    <PageShell eyebrow="Admin" title={spec.title} description={spec.description} actions={<>
      <Link to="/admin/configuration-profiles" className="rounded-lg border border-border px-3 py-2 type-body hover:bg-muted">Profiles and promotions</Link>
      {canCreate && <Link to="/admin/aspc/create" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"><icon.plus className="h-4 w-4" />Create</Link>}
      {canReadDrafts && <Button variant="outline" aria-expanded={showDrafts} onClick={() => setShowDrafts(!showDrafts)}>Copy from setup draft</Button>}
      <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">Admin home</Link>
    </>}>
      {canReadDrafts && showDrafts && <CopySetupConfiguration />}
      <div className="glass-card p-3">
        {canReadDrafts && <p className="mb-3 type-body-sm text-muted-foreground">This page creates configurations for registered assays. For an unpublished assay, add or import its configuration in <Link to="/admin/assay-setups" className="text-primary underline">Assay setup</Link> before publishing.</p>}
        <AdminListToolbar state={state} spec={spec} />
        <AdminListContent state={state} spec={spec}>
          <DataTable columns={tableColumns} data={visibleRows} filename="aspc.csv" hideSearch />
        </AdminListContent>
      </div>

      <AdminActionDialog state={state} spec={spec} />
    </PageShell>
  )
}
