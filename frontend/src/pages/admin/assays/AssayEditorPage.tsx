import {
  AdminEditorActions,
  AdminEditorContent,
  SystemRecordNotice,
} from "@/components/admin/AdminEditorControls";
import { useAdminEditor } from "@/components/admin/useAdminEditor";
import { PageShell } from "@/components/layout/PageShell";
import { hasPermission } from "@/lib/access-control";
import { AdminManagedForm } from "@/pages/admin/AdminManagedForm";
import { AssayDiagnoses } from "@/pages/admin/AssayDiagnoses";
import { AssayGeneLists } from "@/pages/admin/AssayGeneLists";
import { submitPayload } from "@/pages/admin/resource-list";
import { type AdminFormMode, type FormSpec } from "@/pages/admin/resource-specs";
import { resource as spec } from "./resource";
import { Link } from "react-router-dom";

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
        {doc && effectiveMode === "view" && <p className="type-body-sm text-muted-foreground">
          Report sections, reportable tiers and report text belong to each assay configuration,
          which can differ by diagnosis and environment.
          {hasPermission(user, "assay.config:list") && <> <Link className="text-primary underline" to="/admin/aspc">View assay configurations</Link>.</>}
        </p>}

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
            <AssayDiagnoses
              key={String(doc.asp_id)}
              aspId={String(doc.asp_id)}
              canEdit={effectiveMode !== "view" && hasPermission(user, "assay.panel:edit")}
            />
          </div>
        )}
        {doc && <AssayGeneLists aspId={String(doc.asp_id)} aspGroup={String(doc.asp_group)} readonly={effectiveMode === "view"} />}
      </AdminEditorContent>
    </PageShell>
  );
}
