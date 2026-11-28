// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { AdminActionDialog, AdminListContent, AdminListToolbar, AdminRowActions } from "@/components/admin/AdminListControls"
import { useAdminList } from "@/components/admin/useAdminList"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import type { ColumnDef } from "@tanstack/react-table"
import { icon } from "@/lib/assets"
import { Link, useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { notifyActionError } from "@/lib/notifications"
import { adminTableColumns, adminFields } from "../resource-list"
import { filters, columns as preferredColumns, resource as spec } from "./resource"

export function AssayConfigurationsPage() {
  const state = useAdminList({ spec, filters, preferredColumns })
  const { data, rows, visibleRows, canCreate } = state
  const navigate = useNavigate()
  const copy = useMutation({
    mutationFn: (identifier: string) => api.get<{ assay_config: Record<string, unknown> }>(`${spec.endpoint}/${encodeURIComponent(identifier)}/context`).then(result => result.data.assay_config),
    onSuccess: copiedDocument => navigate("/admin/aspc/create", { state: { copiedDocument } }),
    onError: error => notifyActionError("Could not copy configuration", error),
  })
  const fields = adminFields(preferredColumns, rows)
  const tableColumns: ColumnDef<Record<string, unknown>>[] = [
    ...adminTableColumns(fields, spec.idKeys[0], data?.roles || {}),
    { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <div className="flex flex-wrap items-center gap-2"><AdminRowActions state={state} spec={spec} row={row.original} />{canCreate && state.canView && <Button variant="outline" size="sm" disabled={copy.isPending} onClick={() => copy.mutate(String(row.original.aspc_id))} aria-label={`Copy ${String(row.original.aspc_id)} as new`}>Copy as new</Button>}</div> },
  ]
  return (
    <PageShell eyebrow="Admin" title={spec.title} description={spec.description} actions={<>
      <Link to="/admin/configuration-profiles" className="rounded-lg border border-border px-3 py-2 type-body hover:bg-muted">Profiles and promotions</Link>
      {canCreate && <Link to="/admin/aspc/create" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"><icon.plus className="h-4 w-4" />Create</Link>}
      <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">Admin home</Link>
    </>}>
      <Surface variant="card" className="p-3">
        <AdminListToolbar state={state} spec={spec} />
        <AdminListContent state={state} spec={spec}>
          <DataTable columns={tableColumns} data={visibleRows} filename="aspc.csv" hideSearch />
        </AdminListContent>
      </Surface>

      <AdminActionDialog state={state} spec={spec} />
    </PageShell>
  )
}
