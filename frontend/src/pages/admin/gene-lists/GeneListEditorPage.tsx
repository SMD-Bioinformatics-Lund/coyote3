import { AdminEditorActions, AdminEditorContent, SystemRecordNotice } from "@/components/admin/AdminEditorControls"
import { useAdminEditor } from "@/components/admin/useAdminEditor"
import { PageShell } from "@/components/layout/PageShell"
import { AdminManagedForm } from "@/pages/admin/AdminManagedForm"
import {
  submitPayload
} from "@/pages/admin/resource-list"
import {
  type AdminFormMode,
  type FormSpec
} from "@/pages/admin/resource-specs"
import { resource as spec } from "./resource"

export function GeneListEditorPage({ mode }: { mode: AdminFormMode }) {
  const state = useAdminEditor({ spec, mode, documentKey: "genelist", requestBodyKey: "config" })
  const { effectiveMode, form, values, setValues, saveMutation, editorError, setEditorError, navigate } = state
  return (
    <PageShell eyebrow="Admin" title={(effectiveMode === "create" ? "Create " : effectiveMode === "view" ? "View " : "Edit ") + spec.title} description={spec.description} actions={<AdminEditorActions state={state} spec={spec} mode={mode} supportsConfigurationTransfer />}>
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
