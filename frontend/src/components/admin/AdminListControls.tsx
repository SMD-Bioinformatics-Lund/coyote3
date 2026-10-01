import { AppLoader } from "@/components/layout/AppLoader"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import {
  resourceFilterOptionLabel,
  rowDisplayName,
  rowId
} from "@/pages/admin/resource-list"
import {
  type AdminResourceSpec
} from "@/pages/admin/resource-specs"
import { Edit, Eye, MailPlus, Power, Search, Trash2 } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import type { AdminListState } from "./useAdminList"

export function AdminListToolbar({ state, spec }: { state: AdminListState; spec: AdminResourceSpec }) {
  const { q, setQ, resourceFilters, setResourceFilters, listFilterDefinitions, listFilterOptions, visibleRows, rows } = state
  return (
    <div className="mb-3 flex flex-wrap items-end gap-2">
      <div className="relative w-full max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={`Search ${spec.title.toLowerCase()}...`}
          className="w-full rounded-lg border border-input bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
      </div>
      {listFilterDefinitions.map((definition, index) => (
        <label key={definition.field} className="grid min-w-52 gap-1">
          <span className="type-meta font-bold uppercase text-muted-foreground">{definition.label}</span>
          <select
            value={resourceFilters[definition.field] || ""}
            onChange={(event) => {
              const nextFilters = { ...resourceFilters, [definition.field]: event.target.value }
              listFilterDefinitions.slice(index + 1).forEach(({ field }) => {
                delete nextFilters[field]
              })
              setResourceFilters(nextFilters)
            }}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          >
            <option value="">{definition.allLabel}</option>
            {(listFilterOptions[definition.field] || []).map((option) => (
              <option key={option} value={option}>{resourceFilterOptionLabel(definition.field, option)}</option>
            ))}
          </select>
        </label>
      ))}
      <span className="pb-2 text-xs font-semibold text-muted-foreground">
        {visibleRows.length === rows.length ? `${rows.length} loaded` : `${visibleRows.length} of ${rows.length} loaded`}
      </span>
    </div>
  )
}

export function AdminListContent({ state, spec, children }: { state: AdminListState; spec: AdminResourceSpec; children: ReactNode }) {
  const { accessQuery, canList, isLoading, error } = state
  return <>
    {accessQuery.isLoading ? (
      <AppLoader label="Checking administration access" />
    ) : !canList ? (
      <div className="rounded-lg border border-warn/30 bg-warn/10 p-4 text-sm text-warn">
        You do not have permission to list {spec.title.toLowerCase()}.
      </div>
    ) : isLoading ? (
      <AppLoader label={`Loading ${spec.title.toLowerCase()}`} />
    ) : error ? (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        {error instanceof Error ? error.message : "Unable to load resource"}
      </div>
    ) : (
      children
    )}
  </>
}

export function AdminRowActions({ state, spec, row, protectIdentity = false, allowInvite = false }: { state: AdminListState; spec: AdminResourceSpec; row: Record<string, unknown>; protectIdentity?: boolean; allowInvite?: boolean }) {
  const { canView, canEdit, canCreate, canDelete, setPendingAction, mutate } = state
  const id = rowId(row, spec)
  const systemManaged = Boolean(row.system_managed)
  const systemPermission = protectIdentity && systemManaged
  return (
    <div className="flex items-center gap-1">
      {canView && <Link
        to={`/admin/${spec.key}/${encodeURIComponent(id)}/view`}
        className="rounded-md p-1.5 text-primary hover:bg-primary/10"
        title="View"
      >
        <Eye className="h-4 w-4" />
      </Link>}
      {canEdit && !systemPermission && <Link
        to={`/admin/${spec.key}/${encodeURIComponent(id)}/edit`}
        className="rounded-md p-1.5 text-panel hover:bg-panel/10"
        title="Edit"
      >
        <Edit className="h-4 w-4" />
      </Link>}
      {spec.canToggle && canEdit && !systemPermission && (
        <button
          onClick={() =>
            setPendingAction({ action: "toggle", id, name: rowDisplayName(row, spec) })
          }
          disabled={mutate.isPending}
          className="rounded-md p-1.5 text-validation hover:bg-validation/10"
          title="Toggle active"
        >
          <Power className="h-4 w-4" />
        </button>
      )}
      {allowInvite && canCreate && (
        <button
          onClick={() => setPendingAction({ action: "invite", id, name: rowDisplayName(row, spec) })}
          disabled={mutate.isPending}
          className="rounded-md p-1.5 text-rna hover:bg-rna/10"
          title="Invite user"
        >
          <MailPlus className="h-4 w-4" />
        </button>
      )}
      {spec.canDelete && canDelete && !systemManaged && (
        <button
          onClick={() => setPendingAction({ action: "delete", id, name: rowDisplayName(row, spec) })}
          disabled={mutate.isPending}
          className="rounded-md p-1.5 text-destructive hover:bg-destructive/10"
          title="Delete"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

export function AdminActionDialog({ state, spec }: { state: AdminListState; spec: AdminResourceSpec }) {
  const { pendingAction, setPendingAction, mutate } = state
  return <>
    {pendingAction && (
      <ConfirmationDialog open title={`Confirm ${pendingAction.action}`}
        variant={pendingAction.action === "delete" ? "destructive" : "default"}
        description={pendingAction.action === "delete"
          ? `Delete ${spec.title.toLowerCase()} ${pendingAction.name}? This removes the active resource from the admin workflow.`
          : `Apply ${pendingAction.action} to ${spec.title.toLowerCase()} ${pendingAction.name}?`}
        isPending={mutate.isPending}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => mutate.mutate(pendingAction)}
      />
    )}
  </>
}
