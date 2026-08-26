import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Activity, AlertTriangle, CopyPlus, Download, Edit, Eye, LockKeyhole, MailPlus, Plus, Power, Search, Trash2, Upload } from "lucide-react"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { JsonDocumentEditor } from "@/components/admin/JsonDocumentEditor"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { downloadJson } from "@/lib/json-download"
import { cn } from "@/lib/utils"
import { TABLE_PAGE_SIZE_OPTIONS } from "@/lib/user-settings"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import {
  actionLabels,
  specs,
  type AdminFormMode,
  type FormSpec,
} from "@/pages/admin/resource-specs"
import {
  adminCell,
  adminExportValue,
  adminFields,
  formStateFromSpec,
  mutationDisplayName,
  mutationResourceId,
  resourceDocFromContext,
  resourceFilterOptionLabel,
  resourceFilterValues,
  resourceListFilters,
  rowDisplayName,
  rowId,
  rowMatchesResourceFilters,
  submitPayload,
  titleize,
} from "@/pages/admin/resource-list"
import { AdminManagedForm } from "@/pages/admin/resource-form"
import { PermissionCategoryOverview } from "@/pages/admin/permission-category-overview"

export function AdminResourcePage() {
  const { resource = "users" } = useParams()
  const spec = specs[resource] ?? specs.users
  const accessQuery = useCurrentUserAccess()
  const user = accessQuery.data
  const canList = hasPermission(user, spec.permissions.list)
  const canView = hasPermission(user, spec.permissions.view)
  const canCreate = hasPermission(user, spec.permissions.create)
  const canEdit = hasPermission(user, spec.permissions.edit)
  const canDelete = hasPermission(user, spec.permissions.delete)
  const queryClient = useQueryClient()
  const [q, setQ] = useState("")
  const [resourceFilters, setResourceFilters] = useState<Record<string, string>>({})
  const [pendingAction, setPendingAction] = useState<{ action: "toggle" | "delete" | "invite"; id: string; name: string } | null>(null)

  useEffect(() => {
    setResourceFilters({})
  }, [spec.key])

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "admin-resource",
      spec.key,
      q,
      spec.key === "samples" ? resourceFilters.asp_group || "" : "",
      spec.key === "samples" ? resourceFilters.asp_id || "" : "",
    ],
    queryFn: () => {
      const params = new URLSearchParams()
      if (q) params.set(spec.searchParam ?? "q", q)
      if (spec.key === "samples" && resourceFilters.asp_group) {
        params.set("asp_group", resourceFilters.asp_group)
      }
      if (spec.key === "samples" && resourceFilters.asp_id) {
        params.set("asp_id", resourceFilters.asp_id)
      }
      params.set("per_page", String(Math.max(...TABLE_PAGE_SIZE_OPTIONS)))
      return api.get(`${spec.endpoint}?${params.toString()}`).then((res) => res.data)
    },
    enabled: canList,
  })

  const mutate = useMutation({
    mutationFn: ({ action, id }: { action: "toggle" | "delete" | "invite"; id: string; name: string }) => {
      if (action === "invite") return api.post(`${spec.endpoint}/${id}/invite`, {})
      if (action === "toggle") return api.patch(`${spec.endpoint}/${id}/status`, {})
      return api.delete(`${spec.endpoint}/${id}`)
    },
    onSuccess: (result, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      if (spec.key === "samples") {
        queryClient.invalidateQueries({ queryKey: ["samples"] })
        queryClient.invalidateQueries({ queryKey: ["sample-navigation-counts"] })
      }
      setPendingAction(null)
      const displayName = mutationDisplayName(result, variables.name)
      const resourceId = mutationResourceId(result, variables.id)
      notifySuccess(
        `${spec.title} ${actionLabels[variables.action]}`,
        `${displayName} was ${actionLabels[variables.action]}.`,
        `Admin ${spec.key}`,
        {
          type: spec.key,
          id: resourceId,
          name: displayName,
          sampleName: spec.key === "samples" ? displayName : undefined,
        }
      )
    },
    onError: (error, variables) => {
      notifyActionError(
        `Unable to ${variables.action} ${spec.title.toLowerCase()}`,
        error,
        `Admin ${spec.key}`,
        {
          type: spec.key,
          id: variables.id,
          name: variables.name,
          sampleName: spec.key === "samples" ? variables.name : undefined,
        }
      )
    },
  })

  const rows = useMemo(() => (data?.[spec.listKey] || []) as any[], [data, spec.listKey])
  const listFilterDefinitions = useMemo(() => resourceListFilters(spec.key), [spec.key])
  const listFilterOptions = useMemo(() => {
    return Object.fromEntries(listFilterDefinitions.map((definition, index) => {
      const serverOptions = data?.filter_options?.[definition.field]
      if (spec.key === "samples" && Array.isArray(serverOptions)) {
        return [definition.field, serverOptions]
      }
      const parentDefinitions = listFilterDefinitions.slice(0, index)
      const candidateRows = rows.filter((row) =>
        rowMatchesResourceFilters(row, parentDefinitions, resourceFilters)
      )
      const options = Array.from(
        new Set(candidateRows.flatMap((row) => resourceFilterValues(row, definition.field)))
      ).sort((left, right) => left.localeCompare(right))
      return [definition.field, options]
    })) as Record<string, string[]>
  }, [data?.filter_options, listFilterDefinitions, resourceFilters, rows, spec.key])
  const visibleRows = useMemo(() => {
    return rows.filter((row) => rowMatchesResourceFilters(row, listFilterDefinitions, resourceFilters))
  }, [listFilterDefinitions, resourceFilters, rows])
  const fields = useMemo(() => adminFields(spec.key, rows), [spec.key, rows])
  const columns: ColumnDef<any, any>[] = [
    ...fields.map((field): ColumnDef<any, any> => ({
      id: field,
      header: titleize(field),
      accessorFn: (row) => adminExportValue(field, row),
      cell: ({ row }) => adminCell(field, row.original, {
        roleColors: data?.roles || {},
        primaryIdentifier: field === spec.idKeys[0],
      }),
      meta: {
        exportValue: (row: any) => adminExportValue(field, row),
        cellClassName: field === "permissions" ? "min-w-64" : undefined,
      },
    })),
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => {
        const id = rowId(row.original, spec)
        const systemPermission = spec.key === "permissions" && Boolean(row.original.system_managed)
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
                  setPendingAction({ action: "toggle", id, name: rowDisplayName(row.original, spec) })
                }
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-validation hover:bg-validation/10"
                title="Toggle active"
              >
                <Power className="h-4 w-4" />
              </button>
            )}
            {spec.key === "users" && canCreate && (
              <button
                onClick={() => setPendingAction({ action: "invite", id, name: rowDisplayName(row.original, spec) })}
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-rna hover:bg-rna/10"
                title="Invite user"
              >
                <MailPlus className="h-4 w-4" />
              </button>
            )}
            {spec.canDelete && canDelete && !systemPermission && (
              <button
                onClick={() => setPendingAction({ action: "delete", id, name: rowDisplayName(row.original, spec) })}
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-destructive hover:bg-destructive/10"
                title="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            {systemPermission && (
              <span
                className="rounded-md p-1.5 text-muted-foreground"
                title="System permission definitions are read-only and are assigned through roles."
              >
                <LockKeyhole className="h-4 w-4" />
              </span>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <PageShell
      eyebrow="Admin"
      title={spec.title}
      description={spec.description}
      actions={
        <>
          {canCreate && <Link
            to={`/admin/${spec.key}/create`}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"
          >
            <Plus className="h-4 w-4" />
            Create
          </Link>}
          <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            Admin home
          </Link>
        </>
      }
    >
      <div className="glass-card p-3">
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
              <span className="text-[0.68rem] font-bold uppercase text-muted-foreground">{definition.label}</span>
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
          <DataTable columns={columns} data={visibleRows} filename={`${spec.key}.csv`} hideSearch />
        )}
      </div>

      {spec.key === "permissions" && canList && <PermissionCategoryOverview rows={visibleRows} canEdit={canEdit} />}

      {pendingAction && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4">
          <section className="w-full max-w-md rounded-2xl border border-border bg-card p-4 shadow-lg">
            <div className="flex items-start gap-3">
              <div className={cn(
                "rounded-xl border p-2",
                pendingAction.action === "delete"
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-primary/30 bg-primary/10 text-primary"
              )}>
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-semibold">Confirm {pendingAction.action}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {pendingAction.action === "delete"
                    ? `Delete ${spec.title.toLowerCase()} ${pendingAction.name}? This removes the active resource from the admin workflow.`
                    : `Apply ${pendingAction.action} to ${spec.title.toLowerCase()} ${pendingAction.name}?`}
                </p>
                <div className="mt-4 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setPendingAction(null)}
                    className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={mutate.isPending}
                    onClick={() => mutate.mutate(pendingAction)}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold text-white disabled:opacity-50",
                      pendingAction.action === "delete" ? "bg-destructive" : "bg-primary"
                    )}
                  >
                    {mutate.isPending ? <Activity className="h-4 w-4 animate-spin" /> : null}
                    Confirm
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </PageShell>
  )
}

export function AdminResourceEditorPage({ mode }: { mode: AdminFormMode }) {
  const { resource = "users", id = "" } = useParams()
  const location = useLocation()
  const spec = specs[resource] ?? specs.users
  const accessQuery = useCurrentUserAccess()
  const user = accessQuery.data
  const requiredPermission = mode === "create"
    ? spec.permissions.create
    : mode === "edit"
      ? spec.permissions.edit
      : spec.permissions.view
  const allowed = hasPermission(user, requiredPermission)
  const canEdit = hasPermission(user, spec.permissions.edit)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<string, any>>({})
  const [editorError, setEditorError] = useState("")
  const [aspcCategory, setAspcCategory] = useState<"DNA" | "RNA">("DNA")
  const [pendingImport, setPendingImport] = useState<{
    document: Record<string, any>
    aspcCategory?: "DNA" | "RNA"
  } | null>(null)
  const [hasImportedValues, setHasImportedValues] = useState(false)
  const initialCopyApplied = useRef(false)
  const importInputRef = useRef<HTMLInputElement>(null)

  const isSamples = spec.key === "samples"
  const contextQuery = useQuery({
    queryKey: ["admin-resource-context", spec.key, mode, id, aspcCategory],
    enabled: allowed && (!isSamples || mode !== "create"),
    retry: false,
    queryFn: () => {
      if (mode === "create") {
        const params = spec.key === "aspc" ? `?category=${aspcCategory}` : ""
        return api.get(`${spec.endpoint}/create_context${params}`).then((res) => res.data)
      }
      return api.get(`${spec.endpoint}/${encodeURIComponent(id)}/context`).then((res) => res.data)
    },
  })

  const form = contextQuery.data?.form as FormSpec | undefined
  const doc = resourceDocFromContext(contextQuery.data, spec)
  const systemPermission = spec.key === "permissions" && Boolean(doc?.system_managed)
  const effectiveMode: AdminFormMode = systemPermission && mode === "edit" ? "view" : mode
  const supportsConfigurationTransfer = ["asp", "aspc", "genelists"].includes(spec.key)

  const stageImport = useCallback((source: unknown) => {
    if (!source || typeof source !== "object" || Array.isArray(source)) {
      setEditorError("The selected file must contain one JSON configuration object.")
      return
    }
    const imported = source as Record<string, any>
    let importedAspcCategory: "DNA" | "RNA" | undefined
    if (spec.key === "aspc") {
      const category = String(imported.asp_category || "").toUpperCase()
      if (category === "DNA" || category === "RNA") {
        importedAspcCategory = category
        setAspcCategory(category)
      }
    }
    setHasImportedValues(false)
    setPendingImport({ document: imported, aspcCategory: importedAspcCategory })
    setEditorError("")
  }, [spec.key])

  const handleImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    try {
      stageImport(JSON.parse(await file.text()))
    } catch {
      setEditorError("The selected file is not valid JSON. Export a configuration from Coyote3 or correct the JSON file and try again.")
    }
  }

  useEffect(() => {
    if (!form) return
    if (mode === "create" && pendingImport) {
      if (
        pendingImport.aspcCategory
        && (pendingImport.aspcCategory !== aspcCategory || contextQuery.isFetching)
      ) return
      setValues(formStateFromSpec(form, pendingImport.document))
      setPendingImport(null)
      setHasImportedValues(true)
      return
    }
    if (mode === "create" && hasImportedValues) return
    if (mode === "create" && !initialCopyApplied.current) {
      const copiedDocument = (location.state as { copiedDocument?: unknown } | null)?.copiedDocument
      if (copiedDocument) {
        initialCopyApplied.current = true
        stageImport(copiedDocument)
        return
      }
      initialCopyApplied.current = true
    }
    setValues(formStateFromSpec(form, mode === "edit" || mode === "view" ? doc : null))
  }, [aspcCategory, contextQuery.isFetching, doc, form, hasImportedValues, location.state, mode, pendingImport, stageImport])

  const saveMutation = useMutation({
    mutationFn: (payload: any) => {
      if (isSamples) return api.put(`${spec.endpoint}/${encodeURIComponent(id)}`, { sample: payload })
      const bodyKey = ["asp", "aspc", "genelists"].includes(spec.key) ? "config" : "form_data"
      const body = { [bodyKey]: payload }
      if (mode === "create") return api.post(spec.endpoint, body)
      return api.put(`${spec.endpoint}/${encodeURIComponent(id)}`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      if (spec.key === "samples") {
        queryClient.invalidateQueries({ queryKey: ["samples"] })
        queryClient.invalidateQueries({ queryKey: ["sample-navigation-counts"] })
      }
      const resourceName = String(values.name || values.username || values.email || values.role_id || values.permission_id || values.asp_id || values.aspc_id || values.isgl_id || id || spec.title)
      notifySuccess(
        `${spec.title} ${mode === "create" ? "created" : "updated"}`,
        `${resourceName} was ${mode === "create" ? "created" : "updated"} successfully.`,
        `Admin ${spec.key}`,
        { type: spec.key, id: id || resourceName, name: resourceName }
      )
      navigate(`/admin/${spec.key}`)
    },
    onError: (error) => {
      setEditorError(error instanceof Error ? error.message : "Unable to save resource.")
      notifyActionError(`Unable to save ${spec.title.toLowerCase()}`, error, `Admin ${spec.key}`, {
        type: spec.key,
        id,
        name: String(values.name || values.username || values.email || id || spec.title),
      })
    },
  })

  const editorResourceTitle = isSamples ? "Sample JSON document" : spec.title
  const title = `${effectiveMode === "create" ? "Create" : effectiveMode === "view" ? "View" : "Edit"} ${editorResourceTitle}`

  return (
    <PageShell
      eyebrow="Admin"
      title={title}
      description={spec.description}
      actions={
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
      }
    >
      {accessQuery.isLoading ? (
        <section className="surface-panel flex justify-center p-10">
          <AppLoader label="Checking administration access" />
        </section>
      ) : !allowed ? (
        <section className="surface-panel p-4">
          <h2 className="text-lg font-bold">Access not assigned</h2>
          <p className="mt-2 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
            Your roles do not include <code>{requiredPermission}</code>.
          </p>
        </section>
      ) : isSamples && mode === "create" ? (
        <section className="surface-panel p-4">
          <h2 className="text-lg font-semibold">Samples are created through ingestion</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Submit a validated DNA or RNA manifest through the ingest workspace to create a sample.
          </p>
        </section>
      ) : contextQuery.isLoading ? (
        <section className="surface-panel flex justify-center p-10">
          <AppLoader label="Loading admin form" />
        </section>
      ) : contextQuery.error || (!isSamples && !form) || (isSamples && !doc) ? (
        <section className="surface-panel p-4">
          <h2 className="text-lg font-bold">Unable to load form</h2>
          <p className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {contextQuery.error instanceof Error ? contextQuery.error.message : "The form schema was not returned by the backend."}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            A 403 means the backend denied access to this workflow. A 404 means the requested record was not found; for users, reopen edit from the Users table so the username business key is used.
          </p>
        </section>
      ) : isSamples ? (
        <JsonDocumentEditor
          document={doc as Record<string, unknown>}
          readOnly={effectiveMode === "view"}
          isSaving={saveMutation.isPending}
          serverError={editorError}
          onCancel={() => navigate(`/admin/${spec.key}`)}
          onSave={(sampleDocument) => {
            setEditorError("")
            saveMutation.mutate(sampleDocument)
          }}
        />
      ) : (
        <>
          {systemPermission && (
            <section className="surface-panel flex items-start gap-3 p-3">
              <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div>
                <h2 className="text-sm font-semibold">System permission</h2>
                <p className="text-xs text-muted-foreground">
                  This definition is shipped with Coyote3 and cannot be edited, deactivated, or deleted. Assign or remove it through role policies.
                </p>
              </div>
            </section>
          )}
          {spec.key === "aspc" && mode === "create" && (
            <div className="surface-panel flex items-center justify-between gap-3 p-3">
              <div>
                <h2 className="text-sm font-semibold uppercase">Assay Configuration Type</h2>
                <p className="text-xs text-muted-foreground">Choose the schema before filling the create form.</p>
              </div>
              <div className="inline-flex rounded-lg border border-border bg-background p-1">
                {(["DNA", "RNA"] as const).map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setAspcCategory(category)}
                    className={cn("rounded-md px-3 py-1.5 text-sm font-bold", aspcCategory === category ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          )}
          <AdminManagedForm
            mode={effectiveMode}
            spec={spec}
            form={form as FormSpec}
            values={values}
            setValues={setValues}
            isSaving={saveMutation.isPending}
            error={editorError}
            onCancel={() => navigate(`/admin/${spec.key}`)}
            onSave={() => {
              if (effectiveMode === "view") return
              setEditorError("")
              saveMutation.mutate(submitPayload(form as FormSpec, values, effectiveMode))
            }}
          />
        </>
      )}
    </PageShell>
  )
}
