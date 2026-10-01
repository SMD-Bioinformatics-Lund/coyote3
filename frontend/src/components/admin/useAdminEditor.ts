import type { CurrentUserAccess } from "@/lib/access-control"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import {
  formStateFromSpec
} from "@/pages/admin/resource-list"
import {
  type AdminFormMode,
  type AdminResourceSpec,
  type FormSpec
} from "@/pages/admin/resource-specs"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
const NO_INVALIDATIONS: string[][] = []
export function useAdminEditor({ spec, mode, documentKey, requestBodyKey, protectIdentity = false, usesSchema = true, schemaVariant = "", createQuery = "", importSchemaVariant, transformForm, copyIdentityKey, invalidateKeys = NO_INVALIDATIONS }: {
  spec: AdminResourceSpec; mode: AdminFormMode; documentKey: string; requestBodyKey: string; protectIdentity?: boolean; usesSchema?: boolean; schemaVariant?: string; createQuery?: string; importSchemaVariant?: (document: Record<string, unknown>) => string | undefined; copyIdentityKey?: string; invalidateKeys?: string[][]; transformForm?: (form: FormSpec, user: CurrentUserAccess | undefined) => FormSpec
}) {
  const { id = "" } = useParams()
  const location = useLocation()
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
  const [pendingImport, setPendingImport] = useState<{
    document: Record<string, any>
    schemaVariant?: string
  } | null>(null)
  const [hasImportedValues, setHasImportedValues] = useState(false)
  const initialCopyApplied = useRef(false)
  const importInputRef = useRef<HTMLInputElement>(null)

  const contextQuery = useQuery({
    queryKey: ["admin-resource-context", spec.key, mode, id, schemaVariant],
    enabled: allowed && (usesSchema || mode !== "create"),
    retry: false,
    queryFn: () => {
      if (mode === "create") {
        return api.get(`${spec.endpoint}/create_context${createQuery}`).then((res) => res.data)
      }
      return api.get(`${spec.endpoint}/${encodeURIComponent(id)}/context`).then((res) => res.data)
    },
  })

  const form = useMemo(() => {
    const source = contextQuery.data?.form as FormSpec | undefined
    return source && transformForm ? transformForm(source, user) : source
  }, [contextQuery.data?.form, transformForm, user])
  const doc = contextQuery.data?.[documentKey] || null
  const systemManaged = Boolean(doc?.system_managed)
  const systemPermission = protectIdentity && systemManaged
  const effectiveMode: AdminFormMode = systemPermission && mode === "edit" ? "view" : mode

  const stageImport = useCallback((source: unknown) => {
    if (!source || typeof source !== "object" || Array.isArray(source)) {
      setEditorError("The selected file must contain one JSON configuration object.")
      return
    }
    const imported = source as Record<string, any>
    const importedVariant = importSchemaVariant?.(imported)
    setHasImportedValues(false)
    setPendingImport({ document: imported, schemaVariant: importedVariant })
    setEditorError("")
  }, [importSchemaVariant])

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
        pendingImport.schemaVariant
        && (pendingImport.schemaVariant !== schemaVariant || contextQuery.isFetching)
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
        const identityKey = copyIdentityKey || spec.idKeys[0]
        stageImport({ ...(copiedDocument as Record<string, unknown>), [identityKey]: "" })
        return
      }
      initialCopyApplied.current = true
    }
    setValues(formStateFromSpec(form, mode === "edit" || mode === "view" ? doc : null))
  }, [schemaVariant, contextQuery.isFetching, doc, form, hasImportedValues, location.state, mode, pendingImport, spec.idKeys, copyIdentityKey, stageImport])

  const saveMutation = useMutation({
    mutationFn: (payload: any) => {
      const body = { [requestBodyKey]: payload }
      if (mode === "create") return api.post(spec.endpoint, body)
      return api.put(`${spec.endpoint}/${encodeURIComponent(id)}`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      for (const queryKey of invalidateKeys) queryClient.invalidateQueries({ queryKey })
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

  return { id, accessQuery, user, requiredPermission, allowed, canEdit, navigate, values, setValues, editorError, setEditorError, importInputRef, handleImportFile, contextQuery, form, doc, systemManaged, systemPermission, effectiveMode, saveMutation }
}
export type AdminEditorState = ReturnType<typeof useAdminEditor>
