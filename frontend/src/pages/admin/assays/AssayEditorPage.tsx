import {
  AdminEditorActions,
  AdminEditorContent,
  SystemRecordNotice,
} from "@/components/admin/AdminEditorControls";
import { useAdminEditor } from "@/components/admin/useAdminEditor";
import { PageShell } from "@/components/layout/PageShell";
import { hasPermission } from "@/lib/access-control";
import { AdminManagedForm } from "@/pages/admin/AdminManagedForm";
import { AssaySubpanels } from "@/pages/admin/AssaySubpanels";
import { submitPayload } from "@/pages/admin/resource-list";
import { type AdminFormMode, type FormSpec } from "@/pages/admin/resource-specs";
import { resource as spec } from "./resource";

export function AssayEditorPage({ mode }: { mode: AdminFormMode }) {
  const state = useAdminEditor({ spec, mode, documentKey: "panel", requestBodyKey: "config" });
  const {
    effectiveMode,
    form,
    values,
    setValues,
    saveMutation,
    editorError,
    setEditorError,
    navigate,
    doc,
    user,
  } = state;
  return (
    <PageShell
      eyebrow="Admin"
      title={
        (effectiveMode === "create" ? "Create " : effectiveMode === "view" ? "View " : "Edit ") +
        spec.title
      }
      description={spec.description}
      actions={
        <AdminEditorActions state={state} spec={spec} mode={mode} supportsConfigurationTransfer />
      }
    >
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
            if (effectiveMode === "view") return;
            setEditorError("");
            saveMutation.mutate(submitPayload(form as FormSpec, values, effectiveMode));
          }}
        />
        {doc && (
          <div className="glass-card min-w-0 p-3">
            <AssaySubpanels
              key={String(doc.asp_id)}
              aspId={String(doc.asp_id)}
              canEdit={effectiveMode !== "view" && hasPermission(user, "assay.panel:edit")}
            />
          </div>
        )}
      </AdminEditorContent>
    </PageShell>
  );
}
