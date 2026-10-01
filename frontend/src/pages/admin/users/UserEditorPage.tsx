import { AdminEditorActions, AdminEditorContent, SystemRecordNotice } from "@/components/admin/AdminEditorControls"
import { useAdminEditor } from "@/components/admin/useAdminEditor"
import { PageShell } from "@/components/layout/PageShell"
import type { CurrentUserAccess } from "@/lib/access-control"
import { hasPermission } from "@/lib/access-control"
import { AdminManagedForm } from "@/pages/admin/AdminManagedForm"
import {
  submitPayload
} from "@/pages/admin/resource-list"
import {
  type AdminFormMode,
  type FormSpec
} from "@/pages/admin/resource-specs"
import { resource as spec } from "./resource"
function protectUserAssignments(form: FormSpec, user: CurrentUserAccess | undefined): FormSpec {
  const canAssignRoles = hasPermission(user, "user:role:edit")
  const canAssignScope = hasPermission(user, "user:group:edit")
  return { ...form, fields: Object.fromEntries(Object.entries(form.fields).map(([key, field]) => [key, (key === "roles" && !canAssignRoles) || (["asp_ids", "asp_groups", "environments"].includes(key) && !canAssignScope) ? { ...field, readonly: true } : field])) }
}

export function UserEditorPage({ mode }: { mode: AdminFormMode }) {
  const state = useAdminEditor({ spec, mode, documentKey: "user_doc", requestBodyKey: "form_data", protectIdentity: true, transformForm: protectUserAssignments })
  const { effectiveMode, form, values, setValues, saveMutation, editorError, setEditorError, navigate } = state
  return (
    <PageShell eyebrow="Admin" title={(effectiveMode === "create" ? "Create " : effectiveMode === "view" ? "View " : "Edit ") + spec.title} description={spec.description} actions={<AdminEditorActions state={state} spec={spec} mode={mode} />}>
      <AdminEditorContent state={state}>
        <SystemRecordNotice state={state} />

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

      </AdminEditorContent>
    </PageShell>
  )
}
