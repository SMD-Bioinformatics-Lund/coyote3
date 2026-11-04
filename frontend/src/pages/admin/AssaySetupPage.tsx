import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { DocumentEditorNotice } from "@/components/admin/DocumentEditorNotice"
import { ConfigurationTransfer } from "@/components/admin/ConfigurationTransfer"
import { JsonDocumentEditor } from "@/components/admin/JsonDocumentEditor"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { cn } from "@/lib/utils"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useBlocker, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { AdminManagedForm } from "./AdminManagedForm"
import { formStateFromSpec, submitPayload } from "./resource-list"
import { specs, type FormSpec } from "./resource-specs"
import { SetupNavigation } from "./assay-setup/SetupNavigation"
import { SetupEmptyState } from "./assay-setup/SetupEmptyState"
import { SetupConfigurationsTable } from "./assay-setup/SetupConfigurationsTable"
import { AssayGeneLists } from "./AssayGeneLists"

type Document = Record<string, unknown>
type Content = { panel: Document; scopes: string[]; environments: string[]; gene_lists: Document[]; existing_gene_list_ids?: string[]; configurations: Document[] }
type Setup = { _id: string; asp_id: string; status: "draft" | "submitted" | "published"; revision: number; content: Content; content_editors: string[]; created_by: string; updated_by: string; review_reason: string; reviewer?: string | null; reviewed_by?: string | null; published_by?: string | null }
type SetupSummary = Pick<Setup, "_id" | "asp_id" | "status" | "revision" | "reviewer"> & { content?: { panel?: Document } }
type Context = {
  setup?: Setup
  panel_form: FormSpec
  genelist_form?: FormSpec
  configuration_form?: FormSpec
  diagnoses: { diagnosis_id: string; display_name: string; is_active: boolean }[]
  environments: string[]
  rules?: { _id: string; rule_set_id: string; name: string; content_version: number; scope: { diagnosis_id: string } }[]
  readiness?: { ready: boolean; issues: string[]; warnings?: string[] }
  context_error?: string
  history?: { revision: number; action: string; actor: string; at: string }[]
  reviewers?: { username: string; name: string }[]
}
const emptyContent = (panel: Document): Content => ({ panel, scopes: ["base"], environments: ["production"], gene_lists: [], configurations: [] })
const writePermissions = ["assay.panel:create", "assay.panel:edit", "assay.config:create", "gene_list.insilico:create"]

function ResourceEditor({ kind, form, source, readonly, pending, onSave, onCancel, saveLabel, onDirtyChange }: {
  kind: "asp" | "aspc" | "genelists"; form: FormSpec; source: Document; readonly: boolean; pending: boolean
  onSave: (document: Document) => void; onCancel: () => void
  saveLabel?: string
  onDirtyChange: (dirty: boolean) => void
}) {
  const [initialValues] = useState(() => formStateFromSpec(form, source))
  const [values, setValues] = useState(initialValues)
  const [error, setError] = useState("")
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues)
  useEffect(() => { onDirtyChange(dirty) }, [dirty, onDirtyChange])
  useEffect(() => () => onDirtyChange(false), [onDirtyChange])
  const stagedForm = { ...form, fields: { ...form.fields, is_active: { ...form.fields.is_active, hidden_mode: ["create", "view"] } } }
  return <AdminManagedForm bottomActions={kind === "aspc"} saveLabel={saveLabel} mode={readonly ? "view" : "create"} spec={specs[kind]} form={stagedForm} values={values} setValues={setValues} isSaving={pending} error={error} onCancel={onCancel} onSave={() => {
    try { onSave(submitPayload(form, values, "create")) } catch (err) { setError(err instanceof Error ? err.message : "Check the form values") }
  }} />
}

function ScopeEditor({ content, context, readonly, pending, onSave, onRefresh, onDirtyChange }: { content: Content; context: Context; readonly: boolean; pending: boolean; onSave: (content: Content) => void; onRefresh: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const [scopes, setScopes] = useState(content.scopes)
  const [initialEnvironments] = useState(() => [...new Set(["production", ...content.environments])])
  const [environments, setEnvironments] = useState(initialEnvironments)
  const dirty = JSON.stringify(scopes) !== JSON.stringify(content.scopes) || JSON.stringify(environments) !== JSON.stringify(initialEnvironments)
  useEffect(() => { onDirtyChange(dirty) }, [dirty, onDirtyChange])
  useEffect(() => () => onDirtyChange(false), [onDirtyChange])
  const toggle = (items: string[], value: string) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
  return <section aria-label="Scope selection" className="surface-panel min-w-0 space-y-6 p-4 sm:p-6">
    {!readonly && <div className="flex flex-wrap items-center justify-end gap-3"><Link to="/admin/diagnoses" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-primary underline"><icon.layers className="size-4" />Manage diagnosis definitions</Link><Button variant="outline" size="icon" aria-label="Refresh diagnosis definitions" title="Refresh diagnosis definitions" onClick={onRefresh}><icon.refreshCw /></Button></div>}
    <p className="type-body-sm text-muted-foreground">Link the diagnoses this assay supports. A diagnosis can use both panel and whole-genome assays. Assay names and covered genes do not create these links automatically.</p>
    <fieldset disabled={readonly || pending} className="space-y-3"><legend className="type-title mb-3">Supported diagnoses</legend>
      <label className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 p-3"><input type="checkbox" checked disabled />Base<span aria-hidden="true" className="ml-auto type-meta text-muted-foreground">Default scope</span></label>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{context.diagnoses.filter((scope) => scope.diagnosis_id !== "base" && (scope.is_active || scopes.includes(scope.diagnosis_id))).map((scope) => <label key={scope.diagnosis_id} className={cn("flex min-w-0 items-center gap-3 rounded-lg border p-3 type-body transition-colors", scopes.includes(scope.diagnosis_id) ? "border-primary/30 bg-primary/5" : "border-border hover:bg-muted/40")}><input type="checkbox" checked={scopes.includes(scope.diagnosis_id)} onChange={() => setScopes(toggle(scopes, scope.diagnosis_id))} /><span className="min-w-0 break-words">{scope.display_name}{!scope.is_active && " (retired)"}</span></label>)}</div>
    </fieldset>
    <fieldset disabled={readonly || pending} className="space-y-3 border-t border-border pt-4"><legend className="type-title pr-3">Configuration environments</legend><p className="type-body-sm text-muted-foreground">Only Base / production is required for activation. Other configurations are optional and can be added later from Assay Configurations.</p><div className="flex flex-wrap gap-2">{context.environments.map((env) => <label key={env} className={cn("flex items-center gap-3 rounded-lg border px-4 py-3 type-body", environments.includes(env) ? "border-primary/30 bg-primary/5" : "border-border")}><input type="checkbox" checked={environments.includes(env)} disabled={env === "production"} onChange={() => setEnvironments(toggle(environments, env))} />{env}{env === "production" && <span className="type-meta text-muted-foreground">Required</span>}</label>)}</div></fieldset>
    {!readonly && <Button disabled={pending} onClick={() => onSave({ ...content, scopes, environments })}><icon.save />Save and continue</Button>}
  </section>
}

export function AssaySetupPage() {
  const access = useCurrentUserAccess()
  const user = access.data
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const selected = params.get("setup") || (location.pathname === "/admin/asp/create" ? "new" : "")
  const isNew = selected === "new"
  const [step, setStep] = useState(0)
  const [editing, setEditing] = useState<number | null>(null)
  const [configurationSeed, setConfigurationSeed] = useState<Document>({})
  const [reason, setReason] = useState("")
  const [assignee, setAssignee] = useState("")
  useEffect(() => { setAssignee(""); setReason(""); setEditing(null) }, [selected])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [imported, setImported] = useState<Document | null>(null)
  const [dirty, setDirtyState] = useState(false)
  const dirtyRef = useRef(false)
  const setDirty = useCallback((value: boolean) => { dirtyRef.current = value; setDirtyState(value) }, [])
  const [pendingChange, setPendingChange] = useState<(() => void) | null>(null)
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirtyRef.current && (
    currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search
  ))
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault() }
    window.addEventListener("beforeunload", beforeUnload)
    return () => window.removeEventListener("beforeunload", beforeUnload)
  }, [dirty])
  const requestChange = (change: () => void) => {
    if (dirty) setPendingChange(() => change)
    else change()
  }
  const client = useQueryClient()
  const canView = hasPermission(user, "assay.panel:view") && hasPermission(user, "assay.panel:list")
  const canWrite = writePermissions.every((permission) => hasPermission(user, permission))
  const list = useQuery({ queryKey: ["assay-setups"], enabled: canView, queryFn: () => api.get<{ items: SetupSummary[] }>("/admin/assay-setups").then((r) => r.data.items) })
  const context = useQuery({ queryKey: ["assay-setup-context", selected], refetchOnWindowFocus: false, enabled: canView && Boolean(selected) && (!isNew || canWrite), queryFn: () => api.get<Context>(`/admin/assay-setups/${isNew ? "context" : `${encodeURIComponent(selected)}/context`}`).then((r) => r.data) })
  const setup = context.data?.setup
  const content = setup?.content
  const sharedListAccess = !content?.existing_gene_list_ids?.length || hasPermission(user, "gene_list.insilico:edit")
  const documentEditor = useDocumentEditor("assay-setups", selected, canWrite && Boolean(setup) && setup?.status === "draft", async () => {
    const result = await context.refetch()
    if (result.error) throw result.error
  })
  const readonly = !canWrite || !sharedListAccess || !documentEditor.owned || (setup != null && setup.status !== "draft")
  const mutation = useMutation({
    mutationFn: ({ content: next, action }: { content?: Content; action?: string; nextStep?: number }) => action
      ? api.post<Setup>(`/admin/assay-setups/${selected}/${action}`, { revision: setup?.revision, reason, ...(action === "submit" ? { assignee } : {}) }, documentEditor.options())
      : isNew ? api.post<Setup>("/admin/assay-setups", next) : api.put<Setup>(`/admin/assay-setups/${selected}`, { revision: setup?.revision, content: next }, documentEditor.options()),
    onSuccess: async (response, variables) => {
      setDirty(false)
      setPendingChange(null)
      setParams({ setup: response.data._id })
      setEditing(null)
      setReason("")
      setAssignee("")
      if (variables.nextStep !== undefined) setStep(variables.nextStep)
      else if (isNew) setStep(1)
      await client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      await client.invalidateQueries({ queryKey: ["assay-setups"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      if (variables.action === "publish") {
        void client.invalidateQueries({ queryKey: ["admin-resource"] })
        void client.invalidateQueries({ queryKey: ["admin-resource-context"] })
        void client.invalidateQueries({ queryKey: ["assay-gene-lists"] })
        void client.invalidateQueries({ queryKey: ["diagnosis-assay-options"] })
      }
      notifySuccess(variables.action === "publish" ? "Assay activated" : variables.action === "submit" ? "Setup submitted for review" : "Setup draft saved")
    },
    onError: (error) => notifyActionError("Assay setup", error),
  })
  const choose = (identifier: string) => requestChange(() => { navigate(`/admin/assay-setups${identifier ? `?setup=${encodeURIComponent(identifier)}` : ""}`); setStep(0); setEditing(null); setReason(""); setDirty(false); mutation.reset() })
  const importSetup = useMutation({
    mutationFn: (document: Document) => api.post<Setup>("/admin/assay-setups", document),
    onSuccess: response => {
      setImported(null); choose(response.data._id)
      void client.invalidateQueries({ queryKey: ["assay-setups"] })
      void client.invalidateQueries({ queryKey: ["assay-setup-context"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      notifySuccess("Assay setup draft imported")
    },
    onError: error => notifyActionError("Import assay setup", error),
  })
  const deletion = useMutation({
    mutationFn: () => api.delete(`/admin/assay-setups/${selected}?revision=${setup!.revision}`, documentEditor.options()),
    onSuccess: () => {
      setConfirmDelete(false); choose("")
      client.removeQueries({ queryKey: ["assay-setup-context", selected], type: "inactive" })
      void client.invalidateQueries({ queryKey: ["assay-setups"] })
      void client.invalidateQueries({ queryKey: ["clinical-rule-authoring-options"] })
      notifySuccess("Unpublished assay setup deleted")
    },
    onError: (error) => notifyActionError("Assay setup deletion failed", error),
  })
  const save = (next: Content, nextStep?: number) => mutation.mutate({ content: next, nextStep })
  const records = step === 2 ? content?.gene_lists || [] : content?.configurations || []
  const form = step === 2 ? context.data?.genelist_form : context.data?.configuration_form
  const field = step === 2 ? "gene_lists" : "configurations"
  const kind = step === 2 ? "genelists" : "aspc"
  const busy = mutation.isPending || importSetup.isPending || deletion.isPending
  const canActivate = canWrite && sharedListAccess
  const reviewAllowed = hasPermission(user, "assay.panel:edit") && setup?.status === "submitted"
  const isAssignedReviewer = setup?.reviewer === user?.username

  return <PageShell className="min-w-0 [&>*]:min-w-0" eyebrow="Admin" title="Assay setup" actions={canWrite ? <Button disabled={busy || isNew} onClick={() => choose("new")}><icon.plus />New assay setup</Button> : undefined}>
    <DocumentEditorNotice editor={documentEditor} />
    {canWrite && !sharedListAccess && setup?.status !== "published" && <p role="alert" className="surface-panel p-3 type-body-sm text-warning">Saving or activating selected shared gene lists requires gene_list.insilico:edit permission. Ask an administrator for access, or clear the staged selections in Gene lists.</p>}
    {access.isLoading ? <AppLoader label="Loading access" /> : !canView ? <p role="alert">Assay list and view permissions are required.</p> : <>
      <ConfigurationTransfer label="assay setup" filename={`${setup?.asp_id || "assay"}-setup`}
        document={content} metadataDocument={setup ? { ...setup, ...content } : content}
        fields={["panel", "scopes", "environments", "gene_lists", "existing_gene_list_ids", "configurations"]}
        required={["panel"]} disabled={busy || imported !== null || dirty}
        onImport={canWrite ? document => { importSetup.reset(); setImported(document) } : undefined} />
      {isNew && canWrite && context.data && <ConfigurationTransfer label="assay identity"
        filename="assay" importLabel="Import assay identity JSON"
        fields={Object.keys(context.data.panel_form.fields)} required={["asp_id"]}
        disabled={busy || imported !== null || dirty}
        onImport={panel => { importSetup.reset(); setImported({ panel, scopes: ["base"], environments: ["production"],
          gene_lists: [], existing_gene_list_ids: [], configurations: [] }) }} />}
      {imported && <section className="surface-panel space-y-3 p-4" aria-label="Import assay setup">
        <p className="type-body-sm">Review the imported configuration and choose an unused assay identifier. Saving creates a draft that can be activated after validation, with optional review.</p>
        <JsonDocumentEditor document={imported} label="Assay setup" allowUnchanged
          onCancel={() => setImported(null)} serverError={importSetup.error?.message}
          onSave={document => importSetup.mutate(document)} isSaving={importSetup.isPending} />
      </section>}
      <section className="surface-panel flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-0 flex-1 space-y-1"><p className="type-label">Saved setups</p>
          <Select label="Saved setups" value={selected} disabled={busy} onValueChange={choose} options={[
            { value: "", label: "Select a setup" },
            ...(isNew ? [{ value: "new", label: "New assay" }] : []),
            ...(list.data || []).map(item => ({ value: item._id, label: `${item.content?.panel?.name || item.content?.panel?.display_name || item.asp_id} · ${item.asp_id} · ${item.status} · Revision ${item.revision}${item.reviewer ? ` · Reviewer: ${item.reviewer}` : ""}` })),
          ]} />
        </div>
        {setup && <span className="inline-flex shrink-0 items-center rounded-md border border-primary/20 bg-primary/5 px-3 py-2 type-body font-medium text-primary">{setup.status} · Revision {setup.revision}</span>}
      </section>
      {(list.error || context.error) && <p role="alert" className="text-destructive">Unable to load assay setup. <Button variant="link" disabled={list.isFetching || context.isFetching} onClick={() => { if (list.error) void list.refetch(); if (context.error) void context.refetch() }}>Retry loading setup</Button></p>}
      {!selected && !list.isLoading && !list.error && <section className="surface-panel p-4 sm:p-6"><SetupEmptyState icon={icon.clipboardCheck} title={list.data?.length ? "No setup selected" : "No saved assay setups"} /></section>}
      {context.isLoading && <AppLoader label="Loading setup" />}
      {context.data && <>
        <SetupNavigation step={step} isNew={isNew} pending={busy} onChange={(index) => { if (index !== step) requestChange(() => { setStep(index); setEditing(null) }) }} />
        {dirty && <p role="status" className="type-body-sm text-muted-foreground">Unsaved changes. Save this form before activation or changing steps.</p>}
        {mutation.error && <p role="alert" className="text-destructive">{mutation.error.message}</p>}
        {context.data.context_error && <p role="alert" className="text-destructive">{context.data.context_error}</p>}
        {step === 0 && <ResourceEditor saveLabel="Save and continue" key={`${selected}-${setup?.revision}`} kind="asp" form={{ ...context.data.panel_form, fields: { ...context.data.panel_form.fields, is_active: { ...context.data.panel_form.fields.is_active, hidden_mode: ["create", "view"] }, ...(setup ? { asp_id: { ...context.data.panel_form.fields.asp_id, readonly: true } } : {}) } }} source={content?.panel || {}} readonly={readonly} pending={busy} onDirtyChange={setDirty} onCancel={() => choose("")} onSave={(panel) => save(content ? { ...content, panel: { ...panel, asp_id: content.panel.asp_id } } : emptyContent(panel), 1)} />}
        {step === 1 && content && <ScopeEditor key={`${selected}-${setup?.revision}`} content={content} context={context.data} readonly={readonly} pending={busy} onDirtyChange={setDirty} onSave={(next) => save(next, 2)} onRefresh={() => void context.refetch()} />}
        {step === 2 && content && <AssayGeneLists aspId={String(content.panel.asp_id)} aspGroup={String(content.panel.asp_group)} readonly={!canWrite || !documentEditor.owned || setup?.status !== "draft"} pending={busy} selected={content.existing_gene_list_ids || []} onChange={(ids) => requestChange(() => save({ ...content, existing_gene_list_ids: ids }))} />}
        {(step === 2 || step === 4) && content && <section aria-label={step === 2 ? "Gene list workspace" : "Configuration workspace"} className="surface-panel min-w-0 space-y-5 p-4 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4"><h2 className="type-title flex items-center gap-2">{step === 2 ? <icon.listTree className="size-5 text-primary" /> : <icon.settings2 className="size-5 text-primary" />}{step === 2 ? "Staged gene lists" : "Scope configurations"}<span className="type-meta text-muted-foreground">({records.length})</span></h2>{!readonly && <Button variant="outline" disabled={!form || busy || editing === records.length} onClick={() => requestChange(() => { setConfigurationSeed({}); setEditing(records.length) })}><icon.plus />{step === 2 ? "Add gene list" : "Add configuration"}</Button>}</div>
          {!form && !readonly && <p role="status" className="type-body text-muted-foreground">{step === 2 ? "Gene list" : "Configuration"} form unavailable. <Button variant="link" onClick={() => void context.refetch()}>Retry</Button></p>}
          {step === 4 && <SetupConfigurationsTable scopes={content.scopes} environments={content.environments} records={records} readonly={readonly} pending={busy} formAvailable={Boolean(form)} onEdit={index => { if (index !== editing) requestChange(() => setEditing(index)) }} onCreate={(scope, environment) => { if (editing !== records.length || configurationSeed.diagnosis_id !== scope || configurationSeed.environment !== environment) requestChange(() => { setConfigurationSeed({ diagnosis_id: scope, environment }); setEditing(records.length) }) }} onRemove={index => requestChange(() => save({ ...content, configurations: records.filter((_, i) => i !== index) }))} />}
          {step === 2 && <ul className="divide-y divide-border">{records.map((record, index) => <li key={index} className="flex flex-wrap items-center justify-between gap-2 py-3"><span className="min-w-0 break-words type-body">{String(record.displayname || record.display_name || record.name || record.isgl_id)}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={!form || busy} onClick={() => { if (index !== editing) requestChange(() => setEditing(index)) }}><icon.edit />{readonly ? "View" : "Edit"}</Button>{!readonly && <Button variant="ghost" size="icon" aria-label={`Remove gene list ${index + 1}`} disabled={busy} onClick={() => requestChange(() => save({ ...content, gene_lists: records.filter((_, i) => i !== index) }))}><icon.trash2 /></Button>}</div></li>)}</ul>}
          {step === 4 && <p className="type-body-sm text-muted-foreground">Base / production is required. Other configurations are optional and can be added later from <Link className="text-primary underline" to="/admin/aspc">Assay Configurations</Link>.</p>}
          {!records.length && editing == null && <SetupEmptyState icon={step === 2 ? icon.listTree : icon.settings2} title={step === 2 ? "No staged gene lists" : "No configurations saved"} description={step === 2 ? "Gene lists are optional unless required by the selected filters." : "Save a Base / production configuration before activation."} />}
          {editing != null && form && <ResourceEditor key={`${selected}-${setup?.revision}-${step}-${editing}-${configurationSeed.diagnosis_id}-${configurationSeed.environment}`} kind={kind} form={form} source={records[editing] || (step === 2 ? { asp_ids: [setup?.asp_id], asp_groups: [content.panel.asp_group], diagnosis: ["base"] } : { asp_id: setup?.asp_id, asp_group: content.panel.asp_group, asp_category: content.panel.asp_category, display_name: content.panel.display_name, platform: content.panel.platform, diagnosis_id: "base", environment: content.environments[0], ...configurationSeed })} readonly={readonly} pending={busy} onDirtyChange={setDirty} onCancel={() => requestChange(() => setEditing(null))} onSave={(record) => { const next = [...records]; next[editing] = record; save({ ...content, [field]: next }) }} />}
        </section>}
        {step === 3 && content && <section aria-label="Reporting rule workspace" className="surface-panel min-w-0 space-y-5 p-4 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4"><h2 className="type-title flex items-center gap-2"><icon.fileCheck className="size-5 text-primary" />Published reporting rules</h2><div className="flex flex-wrap items-center gap-2"><Link className="inline-flex items-center gap-2 text-primary underline" to="/admin/clinical-rules" target="_blank" rel="noopener noreferrer">Open rule builder</Link><Button variant="outline" size="icon" aria-label="Refresh reporting rules" title="Refresh reporting rules" onClick={() => void context.refetch()}><icon.refreshCw /></Button></div></div>
          <ul className="divide-y divide-border">{(context.data.rules || []).map((rule) => <li key={rule._id} className="flex flex-wrap items-center gap-2 py-3"><icon.check className="size-4 text-pass" /><span className="type-body">{rule.scope.diagnosis_id} · {rule.name} · v{rule.content_version}</span></li>)}</ul>
          {!context.data.rules?.length && <p role="alert" className="rounded-md border border-warning p-3 type-body">Reporting rules are optional. You can complete assay setup now. Reports will be available without an automatically generated summary until compatible rules are published.</p>}
        </section>}
        {step === 5 && setup && <section className="surface-panel min-w-0 space-y-5 p-4 sm:p-6"><h2 className="type-title flex items-center gap-2 border-b border-border pb-4"><icon.clipboardCheck className="size-5 text-primary" />Review and activation</h2><dl className="grid gap-5 type-body sm:grid-cols-2 [&_dd]:mt-1 [&_dd]:break-words [&>div]:min-w-0"><div><dt className="type-label text-muted-foreground">Assay</dt><dd>{String(setup.content.panel.display_name)} ({setup.asp_id})</dd></div><div><dt className="type-label text-muted-foreground">Scopes</dt><dd>{setup.content.scopes.join(", ")}</dd></div><div><dt className="type-label text-muted-foreground">Environments</dt><dd>{setup.content.environments.join(", ") || "None selected"}</dd></div><div><dt className="type-label text-muted-foreground">Created by</dt><dd>{setup.created_by}</dd></div></dl>
          <p className="type-body">Existing gene lists to associate: {setup.content.existing_gene_list_ids?.join(", ") || "None"}</p>
          {setup.reviewer && <p className="type-body">Assigned reviewer: <span className="font-medium">{setup.reviewer}</span></p>}
          {setup.status === "published" && <p className="type-body">Published by: {setup.published_by || "Unknown"} · {setup.reviewed_by ? `Reviewed by ${setup.reviewed_by}` : "Published without review"}</p>}
          {setup.status !== "published" && <div role="status" className={cn("rounded-md border p-3", context.data.readiness?.ready ? "border-pass text-pass" : "border-warning")}>
            <p className="mb-2 flex items-center gap-2 type-body font-medium">{context.data.readiness?.ready ? <icon.check className="size-4 shrink-0" /> : <icon.circleAlert className="size-4 shrink-0 text-warning" />}{context.data.readiness?.ready ? "Ready for activation" : "Setup requires attention"}</p>
            {!context.data.readiness?.ready && <ul className="space-y-2 type-body">{context.data.readiness?.issues.map((issue) => <li className="break-words" key={issue}>{issue}</li>)}</ul>}
          </div>}
          {setup.review_reason && <p className="type-body">Review: {setup.review_reason}</p>}
          {context.data.readiness?.warnings?.map((warning) => <p key={warning} role="alert" className="rounded-md border border-warning p-3 type-body">{warning}</p>)}
          {setup.status !== "published" && <p className="type-body-sm text-muted-foreground">Review is optional. An authorized user can publish and activate this setup once all required checks pass.</p>}
          {setup.status === "draft" && canWrite && <>
            <div className="max-w-lg space-y-2"><p className="type-label">Reviewer for optional review</p><Select label="Reviewer for optional review" value={assignee} disabled={busy || !documentEditor.owned} options={[{ value: "", label: "Select a reviewer" }, ...(context.data.reviewers || []).map(reviewer => ({ value: reviewer.username, label: `${reviewer.name} (${reviewer.username})` }))]} onValueChange={setAssignee} />{!context.data.reviewers?.length && <p className="type-body-sm text-muted-foreground">No eligible reviewer is available. Direct publication is still available with the required permissions.</p>}</div>
            <div className="flex flex-wrap gap-3"><Button disabled={!canActivate || readonly || !context.data.readiness?.ready || busy} onClick={() => mutation.mutate({ action: "publish" })}><icon.check />Publish and activate</Button><Button variant="outline" disabled={!assignee || !documentEditor.owned || !context.data.readiness?.ready || busy} onClick={() => mutation.mutate({ action: "submit" })}><icon.clipboardCheck />Submit for review</Button></div>
          </>}
          {reviewAllowed && <><label className="type-label block">Review notes<textarea className="paper-inset mt-1 min-h-24 w-full rounded-md p-3" value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="flex flex-wrap gap-3">{canWrite && <Button disabled={!canActivate || !context.data.readiness?.ready || busy} onClick={() => mutation.mutate({ action: "publish" })}><icon.check />{isAssignedReviewer ? "Approve and activate" : "Publish and activate"}</Button>}<Button variant="outline" disabled={!reason.trim() || busy} onClick={() => mutation.mutate({ action: "return" })}><icon.arrowLeft />{isAssignedReviewer ? "Return for changes" : "Return to draft"}</Button></div></>}
          {setup.status === "submitted" && !reviewAllowed && <p role="status">Submitted for optional review.</p>}
          {setup.status === "published" && <p role="status">Assay setup published. Manage subsequent changes from the individual resource pages.</p>}
          {setup.status === "published" && <div className="flex flex-wrap gap-3">{hasPermission(user, "assay.panel:view") && <Link className="type-body text-primary underline" to={`/admin/asp/${encodeURIComponent(setup.asp_id)}/view`}>View activated assay</Link>}{hasPermission(user, "assay.config:list") && <Link className="type-body text-primary underline" to="/admin/aspc">Manage assay configurations</Link>}</div>}
          <details><summary className="cursor-pointer type-label">Revision history</summary><ul className="mt-3 divide-y divide-border">{context.data.history?.map((entry) => <li key={entry.revision} className="py-2 type-body">r{entry.revision} · {entry.action} · {entry.actor} · {new Date(entry.at).toLocaleString()}</li>)}</ul></details>
        </section>}
        {!isNew && <footer className="surface-panel flex min-w-0 flex-wrap items-center justify-between gap-2 p-3"><Button variant="outline" disabled={step === 0 || busy} onClick={() => requestChange(() => { setStep(step - 1); setEditing(null) })}><icon.arrowLeft />Previous</Button><span className="type-meta text-muted-foreground">Step {step + 1} of 6{!readonly && (step < 2 || editing !== null) && " · Save the form to continue"}</span><Button variant="outline" disabled={step === 5 || busy || (!readonly && (step < 2 || editing !== null))} onClick={() => requestChange(() => { setStep(step + 1); setEditing(null) })}>Next<icon.arrowRight /></Button></footer>}
      </>}
    </>}
    <ConfirmationDialog open={pendingChange !== null || blocker.state === "blocked"} title="Discard unsaved changes?" description="The changes in this form have not been saved. Your saved draft remains available." confirmLabel="Discard changes" cancelLabel="Keep editing" isPending={busy} onConfirm={() => { const change = pendingChange; setPendingChange(null); setDirty(false); if (blocker.state === "blocked") blocker.proceed(); else change?.() }} onCancel={() => { setPendingChange(null); if (blocker.state === "blocked") blocker.reset() }} />
    {setup && ["draft", "submitted"].includes(setup.status) && hasPermission(user, "assay.panel:delete") && <Button variant="destructive" disabled={busy} onClick={() => setConfirmDelete(true)}><icon.trash2 />Delete unpublished setup</Button>}
    <ConfirmationDialog open={confirmDelete} title="Delete unpublished assay setup?" description="The workspace and its private snapshots will be removed. Separately saved resources and published records are preserved. An audit receipt is retained." confirmLabel="Delete setup" isPending={deletion.isPending} onConfirm={() => deletion.mutate()} onCancel={() => setConfirmDelete(false)} />
  </PageShell>
}
