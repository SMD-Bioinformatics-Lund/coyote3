import { AdminEditorActions, AdminEditorContent, SystemRecordNotice } from "@/components/admin/AdminEditorControls"
import { useAdminEditor } from "@/components/admin/useAdminEditor"
import { PageShell } from "@/components/layout/PageShell"
import { cn } from "@/lib/utils"
import { AdminManagedForm } from "@/pages/admin/AdminManagedForm"
import {
  submitPayload
} from "@/pages/admin/resource-list"
import {
  type AdminFormMode,
  type FormSpec
} from "@/pages/admin/resource-specs"
import { useCallback, useState } from "react"
import { resource as spec } from "./resource"

export function AssayConfigurationEditorPage({ mode }: { mode: AdminFormMode }) {
  const [aspcCategory, setAspcCategory] = useState<"DNA" | "RNA">("DNA")
  const importSchemaVariant = useCallback((document: Record<string, unknown>) => {
    const category = String(document.asp_category || "").toUpperCase()
    if (category !== "DNA" && category !== "RNA") return undefined
    setAspcCategory(category)
    return category
  }, [])
  const state = useAdminEditor({ spec, mode, documentKey: "assay_config", requestBodyKey: "config", schemaVariant: aspcCategory, createQuery: `?category=${aspcCategory}`, importSchemaVariant })
  const { effectiveMode, form, values, setValues, saveMutation, editorError, setEditorError, navigate } = state
  return (
    <PageShell eyebrow="Admin" title={(effectiveMode === "create" ? "Create " : effectiveMode === "view" ? "View " : "Edit ") + spec.title} description={spec.description} actions={<AdminEditorActions state={state} spec={spec} mode={mode} supportsConfigurationTransfer />}>
      <AdminEditorContent state={state}>
        <SystemRecordNotice state={state} />
        {mode === "create" && (
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

      </AdminEditorContent>
    </PageShell>
  )
}
