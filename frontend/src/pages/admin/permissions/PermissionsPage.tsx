// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { Surface } from "@/components/ui/surface"
import { AdminActionDialog, AdminListContent, AdminListToolbar, AdminRowActions } from "@/components/admin/AdminListControls"
import { useAdminList } from "@/components/admin/useAdminList"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import type { ColumnDef } from "@tanstack/react-table"
import { icon } from "@/lib/assets"
import { Link } from "react-router-dom"
import { PermissionCategoryOverview } from "../permission-category-overview"
import { adminTableColumns, adminFields } from "../resource-list"
import { filters, columns as preferredColumns, resource as spec } from "./resource"

export function PermissionsPage() {
  const state = useAdminList({ spec, filters, preferredColumns })
  const { data, rows, visibleRows, canCreate, canList, canEdit } = state
  const fields = adminFields(preferredColumns, rows)
  const tableColumns: ColumnDef<Record<string, unknown>>[] = [
    ...adminTableColumns(fields, spec.idKeys[0], data?.roles || {}),
    { id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <AdminRowActions state={state} spec={spec} row={row.original} /> },
  ]
  return (
    <PageShell eyebrow="Admin" title={spec.title} description={spec.description} actions={<>
      {canCreate && <Link to="/admin/permissions/create" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"><icon.plus className="h-4 w-4" />Create</Link>}
      <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">Admin home</Link>
    </>}>
      <Surface variant="card" className="p-3">
        <AdminListToolbar state={state} spec={spec} />
        <AdminListContent state={state} spec={spec}>
          <DataTable columns={tableColumns} data={visibleRows} filename="permissions.csv" hideSearch />
        </AdminListContent>
      </Surface>
      {canList && <PermissionCategoryOverview rows={visibleRows} canEdit={canEdit} />}
      <AdminActionDialog state={state} spec={spec} />
    </PageShell>
  )
}
