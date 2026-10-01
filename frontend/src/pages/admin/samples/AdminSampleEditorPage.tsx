import { AdminEditorActions, AdminEditorContent } from "@/components/admin/AdminEditorControls"
import { JsonDocumentEditor } from "@/components/admin/JsonDocumentEditor"
import { useAdminEditor } from "@/components/admin/useAdminEditor"
import { PageShell } from "@/components/layout/PageShell"
import {
  type AdminFormMode
} from "@/pages/admin/resource-specs"
import { resource as spec } from "./resource"

const invalidateKeys = [["samples"], ["sample-navigation-counts"]]
export function AdminSampleEditorPage({ mode }: { mode: AdminFormMode }) {
  const state = useAdminEditor({ spec, mode, documentKey: "sample", requestBodyKey: "sample", usesSchema: false, invalidateKeys })
  const { effectiveMode, saveMutation, editorError, setEditorError, navigate, doc } = state
  if (mode === "create" && state.allowed && !state.accessQuery.isLoading) {
    return (
      <PageShell
        eyebrow="Admin"
        title="Create Sample JSON document"
        description={spec.description}
        actions={<AdminEditorActions state={state} spec={spec} mode={mode} />}
      >
        <section className="surface-panel p-4">
          <h2 className="text-lg font-semibold">Samples are created through ingestion</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Submit a validated DNA or RNA manifest through the ingest workspace to create a sample.
          </p>
        </section>
      </PageShell>
    )
  }
  return (
    <PageShell eyebrow="Admin" title={(effectiveMode === "create" ? "Create " : effectiveMode === "view" ? "View " : "Edit ") + "Sample JSON document"} description={spec.description} actions={<AdminEditorActions state={state} spec={spec} mode={mode} />}>
      <AdminEditorContent state={state} usesSchema={false}>

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

      </AdminEditorContent>
    </PageShell>
  )
}
