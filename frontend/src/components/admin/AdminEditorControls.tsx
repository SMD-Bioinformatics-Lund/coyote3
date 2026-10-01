import { AppLoader } from "@/components/layout/AppLoader"
import { downloadJson } from "@/lib/json-download"
import {
  submitPayload
} from "@/pages/admin/resource-list"
import {
  type AdminFormMode,
  type AdminResourceSpec
} from "@/pages/admin/resource-specs"
import { CopyPlus, Download, Edit, LockKeyhole, Upload } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import type { AdminEditorState } from "./useAdminEditor"

export function AdminEditorActions({ state, spec, mode, supportsConfigurationTransfer = false }: { state: AdminEditorState; spec: AdminResourceSpec; mode: AdminFormMode; supportsConfigurationTransfer?: boolean }) {
  const { id, canEdit, systemPermission, importInputRef, handleImportFile, doc, form, values } = state
  return (
    <div className="flex items-center gap-2">
      {mode === "view" && canEdit && !systemPermission && (
        <Link
          to={`/admin/${spec.key}/${encodeURIComponent(id)}/edit`}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"
        >
          <Edit className="h-4 w-4" />
          Edit
        </Link>
      )}
      {supportsConfigurationTransfer && mode === "create" && (
        <>
          <input
            ref={importInputRef}
            type="file"
            accept="application/json,.json"
            className="sr-only"
            aria-label="Import configuration JSON"
            onChange={handleImportFile}
          />
          <button
            type="button"
            onClick={() => importInputRef.current?.click()}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
          >
            <Upload className="h-4 w-4" />
            Import JSON
          </button>
        </>
      )}
      {supportsConfigurationTransfer && mode !== "create" && doc && (
        <button
          type="button"
          onClick={() => downloadJson(`${spec.key}_${String(id)}`, submitPayload(form, values, "create"))}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
        >
          <Download className="h-4 w-4" />
          Export JSON
        </button>
      )}
      {supportsConfigurationTransfer && mode !== "create" && doc && canEdit && (
        <Link
          to={`/admin/${spec.key}/create`}
          state={{ copiedDocument: doc }}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
        >
          <CopyPlus className="h-4 w-4" />
          Copy as new
        </Link>
      )}
      <Link to={`/admin/${spec.key}`} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
        Back to list
      </Link>
    </div>
  )
}

export function SystemRecordNotice({ state }: { state: AdminEditorState }) {
  const { systemPermission, systemManaged } = state
  return <>
    {systemPermission && (
      <section className="surface-panel flex items-start gap-3 p-3">
        <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div>
          <h2 className="text-sm font-semibold">System-installed identity record</h2>
          <p className="text-xs text-muted-foreground">
            This record is maintained by Coyote3 installation tools. Administrative edits, deactivation, and deletion are disabled. Account passwords use the dedicated password workflow.
          </p>
        </div>
      </section>
    )}
    {systemManaged && !systemPermission && (
      <section className="surface-panel flex items-start gap-3 p-3">
        <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div>
          <h2 className="text-sm font-semibold">System-installed record</h2>
          <p className="text-xs text-muted-foreground">
            This record is installed with Coyote3 and cannot be deleted. Authorized users may edit it or deactivate it through the normal managed workflow.
          </p>
        </div>
      </section>
    )}

  </>
}

export function AdminEditorContent({ state, usesSchema = true, children }: { state: AdminEditorState; usesSchema?: boolean; children: ReactNode }) {
  const { accessQuery, allowed, requiredPermission, contextQuery, form, doc } = state
  if (accessQuery.isLoading || (allowed && contextQuery.isLoading)) {
    return (
      <section className="surface-panel flex justify-center p-10">
        <AppLoader label={accessQuery.isLoading ? "Checking administration access" : "Loading admin form"} />
      </section>
    )
  }
  if (!allowed) {
    return (
      <section className="surface-panel p-4">
        <h2 className="text-lg font-bold">Access not assigned</h2>
        <p className="mt-2 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
          Your roles do not include <code>{requiredPermission}</code>.
        </p>
      </section>
    )
  }
  if (contextQuery.error || (usesSchema ? !form : !doc)) {
    return (
      <section className="surface-panel p-4">
        <h2 className="text-lg font-bold">Unable to load form</h2>
        <p className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {contextQuery.error instanceof Error ? contextQuery.error.message : "The form schema was not returned by the backend."}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          A 403 means the backend denied access to this workflow. A 404 means the requested record was not found; for users, reopen edit from the Users table so the username business key is used.
        </p>
      </section>
    )
  }
  return <>{children}</>
}
